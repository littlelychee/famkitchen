# 法米狗私厨 FamKitchen

当前应用版本：`v1.5`

法米狗私厨是一个使用 Django Templates 构建的家庭餐饮排餐系统。它不是前后端分离项目，页面、表单、交互和后端业务都在同一个 Django 应用里完成，适合小家庭先低成本上线、边用边改。

这个项目的核心目标是：让一个家庭可以共同维护菜品库，按日期安排早餐、午餐、晚餐和小零嘴，并把排餐变更或留言通知给家人。

## 当前能力

- 家庭账号
  - 用户注册、登录、退出。
  - 创建家庭、加入家庭、切换当前家庭。
  - 家主和成员角色展示。
  - 家庭邀请码用于邀请新成员。
- 菜品库
  - 新增、编辑、删除菜品。
  - 支持上传菜品图片，没有图片时使用默认插画。
  - 支持 HEIC/HEIF 等图片上传转换能力。
  - 支持早餐、午餐、晚餐、零食等大类。
  - 支持一个菜品绑定多个分类标签。
  - 支持废弃菜品区，普通菜品库不会混入废弃内容。
- 分类栏
  - 分类可按名称正序、倒序、自定义排序。
  - 分类列表高度受顶部和底部操作栏限制，内容多时内部滚动。
  - 新账号或分类很少时，分类按钮不会被拉伸成异常高度。
- 排餐
  - 按日期安排早餐、午餐、晚餐和许愿小零嘴。
  - 添加菜品页支持底部已选栏：查看已选、保存、重置、清空。
  - 菜品可设置数量、备注、辣度、冰量、温热。
  - 保存排餐时可选择提醒家人。
- 消息和通知
  - 排餐变更可生成站内消息。
  - 可给家人发送留言，并在同一留言会话里回复。
  - 有邮箱的成员可以收到邮件通知。
  - 收件人选择使用紧凑 chip 样式，家庭成员多时不会占满页面。
- 采购
  - 底部导航中保留采购入口，作为家庭采购相关功能入口。
- 移动端体验
  - 主要页面按手机宽度设计。
  - 底部固定导航。
  - 顶部显示家庭、版本号和当前账号头像。

## 技术栈

- Python `3.12+`
- Django `5.2`
- SQLite
- Django Templates
- Tailwind CSS CDN
- DaisyUI CDN
- htmx CDN
- Alpine.js CDN
- Lucide icons CDN
- Pillow
- pillow-heif
- 本地上传文件目录：`media/`
- 线上静态文件收集目录：`staticfiles/`

## 目录说明

```text
family_menu/                 Django 项目配置
meals/                       主要业务应用：家庭、菜品、排餐、消息
templates/                   Django 页面模板
templates/base.html          全局布局、顶部栏、底部导航、全局样式和通用脚本
templates/meals/             菜品库、排餐、消息等页面
static/                      图标、默认图片、页面素材
media/                       本地/线上用户上传图片，不应该提交到 Git
db.sqlite3                   本地/线上 SQLite 数据库，不应该提交到 Git
requirements.txt             PythonAnywhere 使用的依赖文件
pyproject.toml               本地 uv 项目配置
DEPLOY_PYTHONANYWHERE.md     首次部署到 PythonAnywhere 的详细说明
UPDATE_PYTHONANYWHERE.md     线上更新流程
```

## 本地运行

项目已经有 `.venv`，平时优先用项目内的 Python：

```bash
cd /Users/zepeng/zepeng/famkitchen
.venv/bin/python manage.py check
.venv/bin/python manage.py migrate
.venv/bin/python manage.py runserver 0.0.0.0:8015
```

打开：

```text
本机访问：http://127.0.0.1:8015/
局域网访问：http://你的 Mac 局域网 IP:8015/
```

如果你想用 `uv` 同步依赖：

```bash
cd /Users/zepeng/zepeng/famkitchen
UV_CACHE_DIR=.uv-cache uv sync
UV_CACHE_DIR=.uv-cache uv run python manage.py check
UV_CACHE_DIR=.uv-cache uv run python manage.py migrate
UV_CACHE_DIR=.uv-cache uv run python manage.py runserver 0.0.0.0:8015
```

如果 8015 被占用，可以临时换端口：

```bash
.venv/bin/python manage.py runserver 0.0.0.0:8001
```

## 本地常用命令

检查 Django 配置：

```bash
.venv/bin/python manage.py check
```

运行测试：

```bash
.venv/bin/python manage.py test
```

检查是否忘记生成迁移：

```bash
.venv/bin/python manage.py makemigrations --check --dry-run
```

执行迁移：

```bash
.venv/bin/python manage.py migrate
```

收集静态文件：

```bash
.venv/bin/python manage.py collectstatic --noinput
```

检查代码补丁是否有尾随空格等问题：

```bash
git diff --check
```

## 主要页面

```text
/accounts/register/                       注册
/accounts/login/                          登录
/family/create/                           创建家庭
/family/join/                             加入家庭
/family/manage/                           管理家庭
/me/                                      个人资料
/dishes/                                  菜品库
/dishes/create/                           新增菜品
/categories/create/                       新增分类
/meal-plan/                               排餐主页
/meal-plan/select/?date=YYYY-MM-DD&meal_type=lunch
                                           给某一餐添加菜品
/meal-plan/share/?date=YYYY-MM-DD         分享某日排餐
/notifications/                           消息列表
/notifications/new/                       新留言
/shopping/                                采购入口
```

## 推荐验收路径

1. 注册用户 A。
2. 创建家庭。
3. 新增几个分类，比如 `包子`、`饮料`、`面条`。
4. 新增菜品，上传图片，选择分类和可调设置。
5. 进入 `/meal-plan/`，选择日期，给早餐或午餐添加菜品。
6. 在添加菜品页试一下底部栏：查看已选、保存、重置、清空。
7. 注册用户 B，用家庭邀请码加入同一个家庭。
8. 用户 A 给用户 B 发送留言，或者保存排餐时提醒用户 B。
9. 用户 B 登录后查看消息和排餐。
10. 检查手机宽度下分类栏是否只在自己的容器内滚动。

## 环境变量

本地开发可以不配置 `.env`，默认 `DEBUG=True`，并允许任意 Host。正式线上不要直接沿用本地默认值。

PythonAnywhere 线上建议使用 `.env`：

```env
DJANGO_SECRET_KEY=替换成很长的随机字符串
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=zepeng.pythonanywhere.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://zepeng.pythonanywhere.com
DJANGO_PUBLIC_SITE_URL=https://zepeng.pythonanywhere.com
DJANGO_MEDIA_URL=/media/
DJANGO_MEDIA_ROOT=/home/zepeng/famkitchen/media
DJANGO_SESSION_COOKIE_SECURE=True
DJANGO_CSRF_COOKIE_SECURE=True
DJANGO_SECURE_SSL_REDIRECT=False
DJANGO_SECURE_HSTS_SECONDS=0

DJANGO_EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
DJANGO_EMAIL_HOST=smtp.gmail.com
DJANGO_EMAIL_PORT=587
DJANGO_EMAIL_HOST_USER=你的gmail地址@gmail.com
DJANGO_EMAIL_HOST_PASSWORD=你的 Gmail 应用专用密码
DJANGO_EMAIL_USE_TLS=True
DJANGO_EMAIL_USE_SSL=False
DJANGO_DEFAULT_FROM_EMAIL=法米狗私厨 <你的gmail地址@gmail.com>
DJANGO_EMAIL_TIMEOUT=15
DJANGO_EMAIL_FAIL_SILENTLY=False
```

生成新的 `DJANGO_SECRET_KEY`：

```bash
.venv/bin/python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

## PythonAnywhere 首次部署摘要

完整首次部署步骤见：

```text
DEPLOY_PYTHONANYWHERE.md
```

核心流程是：

1. 本地把代码提交并推送到 GitHub。
2. PythonAnywhere `Consoles` 里打开 Bash。
3. 克隆仓库到 `~/famkitchen`。
4. 创建虚拟环境并安装依赖。
5. 创建线上 `.env`。
6. 执行 `python manage.py migrate`。
7. 执行 `python manage.py collectstatic --noinput`。
8. 在 PythonAnywhere `Web` 页面选择 `Manual configuration`。
9. 配置 WSGI、虚拟环境、静态文件和媒体文件路径。
10. 点击 `Reload`。

常见路径：

```text
Source code:        /home/zepeng/famkitchen
Working directory:  /home/zepeng/famkitchen
Virtualenv:         /home/zepeng/famkitchen/.venv
Static URL:         /static/
Static directory:   /home/zepeng/famkitchen/staticfiles
Media URL:          /media/
Media directory:    /home/zepeng/famkitchen/media
```

## PythonAnywhere 后续更新线上版本

这是日常发布新版本时最重要的流程。原则是：

- Git 只更新代码。
- PythonAnywhere 上的 `db.sqlite3` 是线上真实数据库，不要用本地数据库覆盖。
- PythonAnywhere 上的 `media/` 是线上真实上传图片，不要用本地 `media/` 覆盖。
- 如果代码包含数据库结构变化，用 Django migration 升级线上数据库。

### 1. 本地先检查

```bash
cd /Users/zepeng/zepeng/famkitchen
git status
.venv/bin/python manage.py check
.venv/bin/python manage.py test
.venv/bin/python manage.py makemigrations --check --dry-run
git diff --check
```

如果有改动，提交并推送：

```bash
git add .
git commit -m "Release v1.5 updates"
git push
```

如果 `git status` 已经干净，就不用重复提交。

### 2. 进入 PythonAnywhere Bash

打开 PythonAnywhere：

```text
Consoles -> Bash
```

进入线上项目：

```bash
cd ~/famkitchen
source .venv/bin/activate
pwd
git status
```

正常路径类似：

```text
/home/zepeng/famkitchen
```

### 3. 更新前备份线上数据

每次更新前建议备份数据库和上传图片：

```bash
cd ~/famkitchen
mkdir -p backups
cp db.sqlite3 backups/db.sqlite3.$(date +%Y%m%d-%H%M%S)
tar -czf backups/media.$(date +%Y%m%d-%H%M%S).tar.gz media
ls -lh backups | tail
```

这一步很重要。它备份的是线上真实数据，不是本地测试数据。

### 4. 拉取最新代码

```bash
cd ~/famkitchen
git pull
```

如果出现冲突，不要继续执行 `migrate` 或 `Reload`。先把冲突信息复制出来，在本地解决后重新推送。

### 5. 更新依赖

```bash
pip install -r requirements.txt
```

即使依赖没有变化，执行一遍通常也安全。

### 6. 执行数据库迁移

```bash
python manage.py migrate
```

如果迁移失败，先不要 Reload。保存错误信息，必要时用前面的备份恢复。

### 7. 收集静态文件

```bash
python manage.py collectstatic --noinput
```

这一步会更新 logo、图标、CSS、页面素材等静态资源。

### 8. 重启 Web app

回到 PythonAnywhere 的 `Web` 页面，找到当前 Web app，点击：

```text
Reload
```

等待页面提示重载完成。

### 9. 上线后检查

打开线上地址：

```text
https://zepeng.pythonanywhere.com
```

至少检查：

```text
/meal-plan/
/dishes/
/notifications/
/me/
```

v1.5 重点检查：

- 顶部显示 `当前版本：v1.5`。
- 菜品库分类栏不会盖住底部导航。
- 新账号或没有类别时，`全部` 按钮不会异常拉长。
- 排餐添加菜品页分类栏停在底部已选栏上方。
- 底部已选栏空状态显示 `已选 0 道`。
- 底部已选栏的 `查看已选`、`保存`、`重置`、`清空` 都能点击。
- 提醒家人/分享/留言的收件人区域是紧凑 chip 样式。
- 消息页标题下只显示家庭名，不再显示保留条数说明。
- 上传图片、登录、注册、排餐保存都正常。

## PythonAnywhere 常见问题

### 页面没变化

先确认线上已经拉到最新代码：

```bash
cd ~/famkitchen
git log --oneline -5
git status
```

然后重新执行：

```bash
python manage.py collectstatic --noinput
```

回到 Web 页面点击 `Reload`。

浏览器里也可以强制刷新，避免看到旧缓存。

### 静态图片或图标不显示

检查 PythonAnywhere `Web` 页面的 Static files：

```text
/static/ -> /home/zepeng/famkitchen/staticfiles
```

然后执行：

```bash
cd ~/famkitchen
source .venv/bin/activate
python manage.py collectstatic --noinput
```

再点 `Reload`。

### 用户上传图片不显示

检查 PythonAnywhere `Web` 页面的 media 配置：

```text
/media/ -> /home/zepeng/famkitchen/media
```

同时确认 `.env` 里：

```env
DJANGO_MEDIA_URL=/media/
DJANGO_MEDIA_ROOT=/home/zepeng/famkitchen/media
```

不要把本地 `media/` 覆盖到线上，除非你明确想替换线上真实图片。

### 迁移失败

先不要 Reload。查看迁移状态：

```bash
cd ~/famkitchen
source .venv/bin/activate
python manage.py showmigrations meals
python manage.py check
```

保留报错信息，再决定是否需要从备份恢复。

### 邮件不发送

检查 `.env` 里的 SMTP 配置，尤其是：

```env
DJANGO_EMAIL_HOST_USER=
DJANGO_EMAIL_HOST_PASSWORD=
DJANGO_DEFAULT_FROM_EMAIL=
```

如果用 Gmail，通常需要应用专用密码，不是邮箱登录密码。

## 数据安全提醒

这些文件和目录不要提交到 Git，也不要随便从本地覆盖线上：

```text
.env
db.sqlite3
media/
staticfiles/
backups/
```

线上最重要的数据是：

```text
/home/zepeng/famkitchen/db.sqlite3
/home/zepeng/famkitchen/media/
```

日常更新只需要 `git pull` 更新代码，然后 `migrate`、`collectstatic`、`Reload`。不需要把线上数据下载下来合并，也不需要重新上传整个项目。
