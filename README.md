# 私家御膳房 MVP

这是一个使用 Django Templates 构建的前后端不分离 MVP。家庭成员可以注册登录、创建或加入家庭、维护共享菜品库，并按日期把菜品加入早餐、午餐、晚餐。

## 技术栈

- Django
- SQLite
- Django Templates
- Tailwind CSS + DaisyUI CDN
- 图片上传到本地 `media/`
- 使用 `uv` 管理项目和 `.venv`

## 本地运行

当前项目已经用 `uv` 初始化，并创建了 `.venv`。如果当前环境可以访问 PyPI，执行：

```bash
UV_CACHE_DIR=.uv-cache uv sync
UV_CACHE_DIR=.uv-cache uv run python manage.py migrate
UV_CACHE_DIR=.uv-cache uv run python manage.py runserver 0.0.0.0:8015
```

打开：

```text
本机访问：http://127.0.0.1:8015/
局域网访问：http://你的Mac局域网IP:8015/
```

当前本地开发配置已允许任意 Host 访问，所以换 Wi-Fi 后不需要再改 `ALLOWED_HOSTS`。正式公网部署时不要沿用这个配置。

## 主要页面

- `/accounts/register/`：注册
- `/accounts/login/`：登录
- `/family/create/`：创建家庭
- `/family/join/`：通过邀请码加入家庭
- `/dishes/`：菜品库
- `/dishes/create/`：新增菜品
- `/categories/create/`：新增分类
- `/meal-plan/`：按日期排早餐、午餐、晚餐

## MVP 验收路径

1. 注册用户 A，创建家庭。
2. 添加分类和菜品，可以上传图片。
3. 在排餐页选择日期，将菜品加入午餐。
4. 注册用户 B，用用户 A 页面显示的邀请码加入同一家庭。
5. 用户 B 刷新后能看到同一菜品库和同一日期的排餐结果。

所有家庭相关查询都按当前登录用户所属家庭过滤，避免不同家庭之间看到或操作彼此数据。
