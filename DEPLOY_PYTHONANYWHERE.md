# PythonAnywhere 部署说明（zepeng）

公网访问地址预计是：

```text
https://zepeng.pythonanywhere.com
```

PythonAnywhere 后台地址是管理入口，不是给用户访问的应用地址。

## 0. 本地先把代码推到 GitHub

当前项目不要提交 `.env`、`db.sqlite3`、`media/` 用户图片、`staticfiles/`、`backups/`。这些已经在 `.gitignore` 里。

如果这个目录还不是 Git 仓库：

```bash
cd /Users/zepeng/zepeng/feeding
git init
git add .
git commit -m "Prepare feeding app for PythonAnywhere"
git branch -M main
git remote add origin <你的 GitHub 仓库地址>
git push -u origin main
```

## 1. PythonAnywhere 拉代码

打开 PythonAnywhere 的 `Consoles`，新建一个 `Bash` console：

```bash
git clone <你的 GitHub 仓库地址> ~/feeding
cd ~/feeding
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 2. 在 PythonAnywhere 创建 `.env`

在 Bash console 里：

```bash
cd ~/feeding
nano .env
```

粘贴下面内容。`DJANGO_SECRET_KEY` 和 `DJANGO_EMAIL_HOST_PASSWORD` 需要填你自己的值：

```env
DJANGO_SECRET_KEY=替换成一个很长的随机字符串
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=zepeng.pythonanywhere.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://zepeng.pythonanywhere.com
DJANGO_PUBLIC_SITE_URL=https://zepeng.pythonanywhere.com
DJANGO_MEDIA_ROOT=/home/zepeng/feeding/media
DJANGO_SESSION_COOKIE_SECURE=True
DJANGO_CSRF_COOKIE_SECURE=True
DJANGO_SECURE_SSL_REDIRECT=False
DJANGO_SECURE_HSTS_SECONDS=0

DJANGO_EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
DJANGO_EMAIL_HOST=smtp.163.com
DJANGO_EMAIL_PORT=465
DJANGO_EMAIL_HOST_USER=zepeng2024@163.com
DJANGO_EMAIL_HOST_PASSWORD=你的163邮箱授权码
DJANGO_EMAIL_USE_TLS=False
DJANGO_EMAIL_USE_SSL=True
DJANGO_DEFAULT_FROM_EMAIL=私家御膳房 <zepeng2024@163.com>
```

保存：`Ctrl+O`，回车，`Ctrl+X`。

生成随机 `DJANGO_SECRET_KEY`：

```bash
cd ~/feeding
source .venv/bin/activate
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

## 3. 初始化数据库和静态文件

```bash
cd ~/feeding
source .venv/bin/activate
python manage.py migrate
python manage.py collectstatic --noinput
```

## 4. 创建 Web app

去 PythonAnywhere 的 `Web` 页面：

1. 点击 `Add a new web app`
2. 域名选 `zepeng.pythonanywhere.com`
3. 选择 `Manual configuration`
4. Python 版本选 `Python 3.12`

创建后在 Web 页面填写：

```text
Source code: /home/zepeng/feeding
Working directory: /home/zepeng/feeding
Virtualenv: /home/zepeng/feeding/.venv
```

## 5. 修改 WSGI 文件

在 Web 页面找到 WSGI configuration file 链接，打开后把内容改成：

```python
import os
import sys

path = "/home/zepeng/feeding"
if path not in sys.path:
    sys.path.insert(0, path)

os.environ["DJANGO_SETTINGS_MODULE"] = "family_menu.settings"

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```

保存。

## 6. 配置静态文件和上传图片

在 Web 页面 `Static files` 区域添加两条：

```text
URL: /static/
Directory: /home/zepeng/feeding/staticfiles
```

```text
URL: /media/
Directory: /home/zepeng/feeding/media
```

然后点击 `Reload`。

## 7. 验证

打开：

```text
https://zepeng.pythonanywhere.com
```

建议检查：

1. 登录/注册是否正常。
2. 创建家庭、添加菜品是否正常。
3. 上传头像或菜品图片是否正常。
4. 分享排餐后，邮件里的按钮是否跳到 `https://zepeng.pythonanywhere.com/meal-plan/?date=...`。

## 8. 后续每次更新代码

在 PythonAnywhere Bash console：

```bash
cd ~/feeding
source .venv/bin/activate
git pull
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
```

然后去 Web 页面点 `Reload`。

## 9. 备份线上数据

线上 SQLite 和图片都在 PythonAnywhere，不会跟 GitHub 走。更新前可以备份：

```bash
cd ~/feeding
mkdir -p backups
cp db.sqlite3 backups/db.sqlite3.$(date +%Y%m%d-%H%M%S)
tar -czf backups/media.$(date +%Y%m%d-%H%M%S).tar.gz media
```

`db.sqlite3` 和 `media/` 是线上真实用户数据，不要用本地文件覆盖。
