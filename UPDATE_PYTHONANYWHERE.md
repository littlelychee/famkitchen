# 法米狗私厨 PythonAnywhere 线上更新流程

这份文档用于把本地已经检查好的版本更新到 PythonAnywhere 线上站点。

## 1. 本地先确认

在本地项目目录执行：

```bash
cd /Users/zepeng/zepeng/famkitchen
git status
.venv/bin/python manage.py check
.venv/bin/python manage.py test
.venv/bin/python manage.py makemigrations --check --dry-run
git diff --check
```

确认测试通过后提交并推送：

```bash
git add .
git commit -m "Release v1.5 updates"
git push
```

如果 `git status` 显示没有需要提交的内容，就不用重复提交。

## 2. 登录 PythonAnywhere

打开 PythonAnywhere，进入 `Consoles`，启动一个 `Bash` console。

进入线上项目目录：

```bash
cd ~/famkitchen
source .venv/bin/activate
```

确认当前目录正确：

```bash
pwd
git status
```

正常应该看到项目路径类似：

```text
/home/zepeng/famkitchen
```

## 3. 更新前备份线上数据

线上真实数据主要是数据库和用户上传图片，不要用本地文件覆盖它们。

```bash
cd ~/famkitchen
mkdir -p backups
cp db.sqlite3 backups/db.sqlite3.$(date +%Y%m%d-%H%M%S)
tar -czf backups/media.$(date +%Y%m%d-%H%M%S).tar.gz media
```

备份完成后可以确认一下：

```bash
ls -lh backups | tail
```

## 4. 拉取最新代码

```bash
cd ~/famkitchen
git pull
```

如果这里提示有冲突，不要继续执行迁移和重启。先把终端里的冲突信息复制出来，再回本地处理。

## 5. 安装依赖

即使依赖没有变化，执行一遍也安全：

```bash
pip install -r requirements.txt
```

## 6. 执行数据库迁移

v1.5 包含前端交互、模板和已有数据结构相关功能更新；每次发布仍建议执行迁移，确保线上数据库和代码一致：

```bash
python manage.py migrate
```

如果迁移失败，先不要 Reload。保留错误信息，必要时可以用第 3 步的备份恢复。

## 7. 收集静态文件

logo、图标、CSS、页面素材更新后，需要收集静态文件：

```bash
python manage.py collectstatic --noinput
```

## 8. 重启线上应用

回到 PythonAnywhere 的 `Web` 页面，找到当前 Web app，点击：

```text
Reload
```

等待页面提示重载完成。

## 9. 上线后检查

打开线上地址：

```text
https://zepeng.pythonanywhere.com
```

至少检查这些页面：

```text
/meal-plan/
/dishes/
/notifications/
/me/
```

重点确认：

- 顶部显示 `当前版本：v1.5`
- 大 logo 显示为法米狗私厨，并按选中的 2、3、4、6、8、9、10 轮换
- 成员账号也能看到并使用分类编辑按钮
- 家庭角色显示为 `家主`、`成员`
- 菜品库分类栏不会盖住底部导航，分类多时可以单独滚动
- 新账号或没有类别时，`全部` 按钮不会异常拉长
- 排餐添加菜品页面分类栏停在底部已选栏上方，分类多时可以单独滚动
- 排餐添加菜品页底部栏显示 `已选 0 道`，并且 `查看已选`、`保存`、`重置`、`清空` 都能点击
- 提醒家人、分享排餐、新留言和回复页面的收件人区域是紧凑 chip 样式
- 消息页标题下只显示家庭名
- 消息页可以新增留言并给成员发邮件
- 菜品详细设置里有 `可温热`
- HEIC/HEIF 图片上传能自动转换

## 10. 如果线上报错

先看 PythonAnywhere 的 `Web` 页面里的日志：

```text
Error log
Server log
```

也可以在 Bash console 里做基础检查：

```bash
cd ~/famkitchen
source .venv/bin/activate
python manage.py check
python manage.py showmigrations meals
```

如果静态文件没更新，重新执行：

```bash
python manage.py collectstatic --noinput
```

然后回 `Web` 页面再次点击 `Reload`。

## 11. 重要提醒

不要把本地的 `db.sqlite3` 或 `media/` 上传覆盖线上，除非你明确想把线上真实数据替换成本地测试数据。

每次上线前都建议先备份：

```bash
cp db.sqlite3 backups/db.sqlite3.$(date +%Y%m%d-%H%M%S)
tar -czf backups/media.$(date +%Y%m%d-%H%M%S).tar.gz media
```
