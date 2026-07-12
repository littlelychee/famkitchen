# 私家御膳房项目 Bug 扫描报告

扫描日期：2026-07-11  
项目路径：`/Users/zepeng/zepeng/feeding`

## 扫描范围

- Django 配置、URL、模型、表单、视图、模板、工具函数、已有测试。
- 运行了 Django 系统检查、迁移一致性检查、测试套件、部署检查。
- 用临时事务复现了几个高风险交互，不写入当前 `db.sqlite3`。
- 当前数据库只做只读观察。

## 验证结果

已通过：

```bash
UV_CACHE_DIR=.uv-cache uv run python manage.py check
UV_CACHE_DIR=.uv-cache uv run python manage.py makemigrations --check --dry-run
UV_CACHE_DIR=.uv-cache uv run python manage.py test
```

结果：

- `manage.py check`：0 个问题。
- `makemigrations --check --dry-run`：No changes detected。
- `manage.py test`：13 个测试全部通过。

部署检查：

```bash
UV_CACHE_DIR=.uv-cache uv run python manage.py check --deploy
```

结果：6 个安全警告，主要集中在 `DEBUG=True`、开发用 `SECRET_KEY`、未启用 HTTPS/HSTS、安全 Cookie。

## Bug 清单

### 1. 普通家庭成员可以直接新建分类

状态：产品确认允许，不作为 bug 修复  
严重程度：无  
位置：

- `templates/meals/dish_list.html:12-14`
- `templates/meals/dish_form.html:10-12`
- `meals/views.py:541-555`

现象：

- 菜品库和新增菜品页里的“新增分类”按钮没有按 owner 权限隐藏。
- `category_create_view` 只检查用户是否登录和是否有家庭，没有检查 `is_family_owner`。
- 普通成员直接 POST `/categories/create/` 可以成功创建分类。

2026-07-11 备注后结论：

- 这是预期行为：普通家庭成员本来就可以参与维护菜品和分类。
- 保持现有新增分类权限，不改成 owner-only。
- 仍保留 owner 对家庭信息和成员管理的权限控制。

复现证据：

```text
member_category_create_status 302
member_category_create_count_delta 1
```

原因分析：

- 分类编辑和删除已经有 owner 检查，但新增分类漏了同样的权限判断。
- 前端只把侧边栏编辑按钮包在 `can_manage_categories` 里，顶部“新增分类”按钮没有包。

修改方案：

1. 在 `category_create_view` 获取家庭后立刻加入 owner 校验：

   ```python
   if not is_family_owner(request.user, family):
       return HttpResponseForbidden("只有家庭创建者可以新增分类。")
   ```

2. 模板中只有 `can_manage_categories` 为真时才展示“新增分类”入口。
3. 补测试：普通成员 GET/POST 新增分类应返回 403，owner 才能创建。

### 2. 编辑分类所属大类后，菜品会残留旧大类链接

严重程度：高  
位置：`meals/views.py:594-618`

现象：

- 把一个分类从“午餐”改到“晚餐”后，相关菜品会新增晚餐链接，但旧的午餐链接不会删除。
- 结果是菜品会同时出现在旧大类和新大类中。

复现证据：

```text
category_move_status 302
category_after_move dinner
dish_legacy_section_after_move dinner
dish_links_after_move ['dinner', 'lunch']
```

原因分析：

- `category_edit_view` 在 `old_meal_section != category.meal_section` 时只执行了 `get_or_create` 新链接。
- 代码没有删除 `DishMealSection` 中旧的 `old_meal_section` 链接。

修改方案：

1. 分类大类变更后，对受影响菜品同步删除旧链接：

   ```python
   DishMealSection.objects.filter(
       dish_id__in=affected_ids,
       meal_section=old_meal_section,
   ).delete()
   ```

2. 再创建新链接，并同步 legacy 字段。
3. 如果某个菜品还有其他分类仍属于旧大类，需要先判断旧大类是否仍被其他分类需要；不要无脑删。
4. 补测试：分类从 lunch 改 dinner 后，菜品不再出现在 lunch 列表，只出现在 dinner 列表。

### 3. 删除分类后，菜品也会残留被删除分类对应的大类链接

严重程度：高  
位置：`meals/views.py:651-684`

现象：

- 菜品同时属于“午餐主食”和“晚餐主食”。
- 删除“午餐主食”后，菜品的小类只剩“晚餐主食”，但大类链接仍保留 `lunch` 和 `dinner`。

复现证据：

```text
category_delete_status 302
dish_primary_after_delete 晚餐主食 dinner
dish_links_after_delete ['dinner', 'lunch']
dish_categories_after_delete [('dinner', '晚餐主食')]
```

原因分析：

- 删除分类时计算了 `remaining_sections`，但没有真正删除被删分类对应的 `DishMealSection`。
- `dish.save(update_fields=["meal_section", "category", "updated_at"])` 只保存 legacy 字段，不会影响多大类关联表。

修改方案：

1. 删除分类后，重新根据菜品剩余小类计算它应该保留的大类链接。
2. 对仍有大类归属的菜品：删除不存在的小类对应的大类链接，保留剩余分类对应的大类。
3. 对没有任何小类/大类归属的菜品：移动到 `discarded`，并删除对应排餐。
4. 补测试：删除一个分类后，菜品不应继续出现在该分类原来的大类里。

### 4. 移动端选择页取消带备注的菜品不会删除排餐项

严重程度：高  
位置：

- `meals/views.py:756-768`
- `meals/views.py:836-846`
- `templates/meals/meal_plan_select.html:31-42`
- `templates/meals/meal_plan_select.html:112-121`

现象：

- 在移动端选择页勾选一个菜品，填写备注或数量。
- 再取消勾选。
- 页面返回 204，但排餐项仍然留在当天菜单中。

复现证据：

```text
toggle_noted_count_before 1
toggle_noted_count_after_uncheck 1
toggle_noted_remaining [('冰镇', 2)]
```

原因分析：

- `selected_ids` 和 `items_by_dish` 只认 `note=""` 的排餐项。
- 取消勾选时也只删除 `note=""` 的排餐项：

  ```python
  MealPlanItem.objects.filter(meal_plan=meal_plan, dish=dish, note="").delete()
  ```

- 一旦用户写了备注，该 item 的 `note` 不为空，取消勾选就删不到它。

修改方案：

1. 明确移动端选择页的语义：
   - 如果 checkbox 表示“这个菜今天要不要出现”，取消时应删除该 meal plan 下这个 dish 的相关 item。
   - 如果要保留同一菜品多条备注记录，页面需要按 item 展示，而不是按 dish 展示。
2. V1 更简单的修法：取消勾选时删除 `meal_plan + dish` 下的全部 item。
3. 更稳的修法：模板带上 `item_id`，后端按具体 item 更新/删除。
4. 补测试：带备注 item 取消勾选后应从 `MealPlanItem` 删除。

### 5. 移动端“保存选择”不会删除未勾选菜品

严重程度：中高  
位置：`meals/views.py:778-791`

现象：

- 移动端选择页底部按钮叫“保存选择”。
- 如果已有菜品被取消勾选，然后提交整个表单，后端只追加/更新已勾选菜品，不删除未勾选菜品。

复现证据：

```text
select_form_save_status 302
select_form_unchecked_before 1
select_form_unchecked_after 1
```

原因分析：

- POST 分支只遍历 `checked_ids` 并保存，没有对 `checked_ids` 外的旧 item 做差集删除。
- 当前逻辑依赖 HTMX checkbox change 请求完成删除；一旦 HTMX 没触发、网络失败、JS 失效，最终保存按钮并不能兜底。

修改方案：

1. 在表单 POST 时计算当前 meal plan 下已有 item 和 `checked_ids` 的差集。
2. 删除 unchecked 对应 item。
3. 如果采用“按 item 管理”方案，则按 `item_id` 精确同步。
4. 补测试：已有 item 未勾选提交后应被删除。

### 6. 已加入多个家庭时，“当前家庭”固定取最早加入的一个

严重程度：中  
位置：`meals/utils.py:8-14`

现象：

- `profile` 页面能显示多个家庭记录。
- 但整个应用的当前家庭始终取 `joined_at` 最早的一条 membership。
- 如果用户已经有家庭，再加入新家庭，重定向到排餐页后仍可能看到旧家庭。

原因分析：

- 当前家庭没有保存在 session，也没有切换入口。
- `get_current_family` 的策略是隐式的：`order_by("joined_at").first()`。

修改方案：

1. 在 session 中保存 `current_family_id`。
2. 创建/加入家庭成功后，把新家庭设为当前家庭。
3. 在“我的”页面给每个家庭加“切换到这个家庭”按钮。
4. 所有入口先验证 session 中的 family 是否属于当前用户，不属于则回退到第一个家庭。

### 7. `section=discarded` 下仍暴露新增分类/新增菜品入口，实际表单又禁止废弃大类

严重程度：中  
位置：

- `templates/meals/dish_list.html:12-14`
- `meals/views.py:424-460`
- `meals/views.py:546-560`
- `meals/forms.py:8-12`
- `meals/forms.py:77-81`
- `meals/forms.py:161-188`

现象：

- 在废弃页点击“新增菜品”会带上 `?meal_section=discarded`。
- `DishForm` 的大类 choices 排除了 `discarded`，提交时也禁止选择废弃。
- 在废弃页点击“新增分类”会带上 `section=discarded`，但分类表单同样排除了废弃大类。

原因分析：

- 列表页把废弃当成普通 section 展示入口。
- 表单层又明确禁止用户手动创建废弃内容，两边语义不一致。

修改方案：

1. 废弃页隐藏“新增分类”和“新增菜品”按钮，或跳转时不带 `discarded` 初始值。
2. `dish_create_view` 只接受 `ACTIVE_DISH_SECTIONS` 作为初始大类。
3. `get_category_return_target` 只允许 active section 作为新增分类初始值。
4. 补测试：`?meal_section=discarded` 不应初始化为非法大类。

### 8. 线上/弱网环境依赖外部 CDN，核心交互可能失效

严重程度：中  
位置：`templates/base.html:9-13`

现象：

- Tailwind、DaisyUI、HTMX、Alpine、Lucide 都从外部 CDN 加载。
- 对家庭局域网使用来说，如果设备没有外网或 CDN 被阻断，样式和交互会明显损坏。
- `alpinejs@3.x.x` 和 `lucide@latest` 不是完全锁定版本，未来可能有不可预期变化。

原因分析：

- MVP 为了快，直接用 CDN。
- 但当前页面的分类编辑、toast、移动端选择页都依赖这些脚本。

修改方案：

1. 把 JS/CSS vendor 到 `static/vendor/`，或引入标准前端构建流程。
2. 锁定具体版本，不使用 `latest`。
3. 给移动端选择页的最终 POST 做完整后端兜底，减少对 HTMX 成功执行的依赖。

### 9. 当前配置只能作为本地开发配置

严重程度：中  
位置：

- `family_menu/settings.py:6-10`
- `README.md:31`

现象：

- `SECRET_KEY` 是硬编码的开发 key。
- `DEBUG=True`。
- `ALLOWED_HOSTS=["*"]`。
- `check --deploy` 报 6 个安全警告。

原因分析：

- README 已明确说“正式公网部署时不要沿用这个配置”，所以这不是本地运行 bug。
- 但如果后续要让别人公网访问或长期运行，这会变成真实安全问题。

修改方案：

1. 拆分 `settings_dev.py` 和 `settings_prod.py`，或用环境变量控制：
   - `DJANGO_SECRET_KEY`
   - `DJANGO_DEBUG`
   - `DJANGO_ALLOWED_HOSTS`
2. 生产环境启用 HTTPS、安全 Cookie、CSRF 安全设置。
3. 部署前让 `manage.py check --deploy` 通过或只保留明确接受的警告。

## 当前数据库只读观察

只读检查结果：

```text
families 1
members 3
categories 6
dishes 3
plans 27
items 0
dish_family_category_mismatch 0
dish_legacy_section_mismatch 1
dish_without_section_links 0
discarded_with_active_links 0
noted_items 0
```

观察：

- 没有发现跨家庭 category mismatch。
- 有 1 个菜品 legacy `meal_section` 与主 `category.meal_section` 不一致：`大学美味`。它同时有多个大类/小类，可能是多大类功能导致的兼容字段不一致，不一定是坏数据。
- 当前没有排餐 item，所以移动端取消备注 item 的 bug 暂时不会污染当前菜单数据。

## 建议修复顺序

1. 先修权限：普通成员不能新增分类，同时隐藏入口。
2. 再修分类同步：分类编辑/删除后，统一重算菜品的大类链接。
3. 再修移动端排餐：取消勾选和最终保存都要能删除旧 item。
4. 补齐上述回归测试。
5. 如果准备长期给家人使用，再本地化 CDN 资源。
6. 如果准备部署到公网，再拆分生产配置并处理 `check --deploy` 警告。

## 建议新增测试

- `CategoryPermissionTests`
  - 普通成员 GET/POST `/categories/create/` 返回 403。
  - owner 可以创建分类。

- `CategorySectionSyncTests`
  - 分类从 lunch 改 dinner 后，关联菜品不再保留 lunch 链接。
  - 删除 lunch 分类后，仍有 dinner 分类的菜品不再保留 lunch 链接。
  - 删除最后一个分类后，菜品移入 discarded，并从排餐移除。

- `MobileMealPlanSelectTests`
  - 带备注 item 取消勾选后被删除。
  - 表单保存时未勾选旧 item 被删除。
