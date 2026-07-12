# PythonAnywhere 线上修复指南

这份文档用于修复两个线上核心问题：

1. 分享发送邮件后，收件人收不到邮件。
2. 用户上传的菜品图片或头像变成坏图。

下面命令默认你的线上项目目录是 `~/famkitchen`。如果你当时部署成了 `~/feeding`，把文档里的 `~/famkitchen` 全部替换成 `~/feeding`。

参考官方说明：

- PythonAnywhere SMTP 限制：https://help.pythonanywhere.com/pages/SMTPForFreeUsers/
- PythonAnywhere Django 静态文件和 media 映射：https://help.pythonanywhere.com/pages/DjangoStaticFiles/

## 1. 先备份线上真实数据

打开 PythonAnywhere 的 `Consoles`，新建 `Bash` console：

```bash
cd ~/famkitchen
mkdir -p backups
cp db.sqlite3 backups/db.sqlite3.$(date +%Y%m%d-%H%M%S)
tar -czf backups/media.$(date +%Y%m%d-%H%M%S).tar.gz media
```

`db.sqlite3` 和 `media/` 是线上真实用户数据，不要用本地文件覆盖它们。

## 2. 拉取这次代码更新

```bash
cd ~/famkitchen
source .venv/bin/activate
git pull
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
```

然后先不要急着点 Reload，继续检查 `.env` 和 Web 页面配置。

## 3. 修复上传图片坏图

编辑线上 `.env`：

```bash
cd ~/famkitchen
nano .env
```

确认至少有这两行：

```env
DJANGO_MEDIA_URL=/media/
DJANGO_MEDIA_ROOT=/home/zepeng/famkitchen/media
```

保存后，去 PythonAnywhere 的 `Web` 页面，在 `Static files` 区域确认有这两条映射：

```text
URL: /static/
Directory: /home/zepeng/famkitchen/staticfiles
```

```text
URL: /media/
Directory: /home/zepeng/famkitchen/media
```

注意：Django 在 `DEBUG=False` 时不会自己帮你托管用户上传文件，PythonAnywhere 必须有 `/media/` 这一条映射。

## 4. 修复邮件发送

PythonAnywhere 免费账号不能随便连接普通 SMTP 服务。比如 `smtp.163.com` 大概率会被免费账号网络限制挡住，所以线上看起来像“发送成功”，实际收件人收不到。

最简单的修复方式是改用 Gmail SMTP + 应用专用密码。把 `.env` 里的邮件配置改成：

```env
DJANGO_EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
DJANGO_EMAIL_HOST=smtp.gmail.com
DJANGO_EMAIL_PORT=587
DJANGO_EMAIL_HOST_USER=你的gmail地址@gmail.com
DJANGO_EMAIL_HOST_PASSWORD=你的Gmail应用专用密码
DJANGO_EMAIL_USE_TLS=True
DJANGO_EMAIL_USE_SSL=False
DJANGO_DEFAULT_FROM_EMAIL=私家御膳房 <你的gmail地址@gmail.com>
DJANGO_EMAIL_TIMEOUT=15
DJANGO_EMAIL_FAIL_SILENTLY=False
```

Gmail 这里不要填你的 Gmail 登录密码，要填 Google 账号里生成的“应用专用密码”。

保存 `.env` 后，在 PythonAnywhere console 里测试：

```bash
cd ~/famkitchen
source .venv/bin/activate
python manage.py shell
```

进入 shell 后粘贴：

```python
from django.core.mail import send_mail
send_mail("FamKitchen 邮件测试", "收到这封邮件，说明 PythonAnywhere 邮件配置已经通了。", None, ["你的收件邮箱"], fail_silently=False)
```

如果返回 `1`，说明 Django 已经把邮件交给 SMTP 服务。然后去收件箱和垃圾邮件里检查。

如果报错，去 PythonAnywhere 的 `Web` 页面看 `Error log`，这次代码已经不会静默吞掉邮件异常，日志里会出现真实失败原因。

## 5. Reload 并验证

回到 PythonAnywhere 的 `Web` 页面，点击：

```text
Reload
```

然后验证：

1. 登录后进入“我的”，上传一张自定义头像，弹窗里应该立刻出现新头像。
2. 保存头像后，顶部头像应该变化。
3. 新建或编辑菜品上传图片，菜品库里应该显示上传图。
4. 分享排餐给有邮箱的家庭成员，收件邮箱应该收到邮件。

如果上传图还是坏图，优先检查 `Web -> Static files` 的 `/media/` 映射路径是不是 `/home/zepeng/famkitchen/media`。

如果邮件还是收不到，优先检查：

1. `.env` 是否仍然写着 `smtp.163.com`。
2. Gmail 是否使用了应用专用密码。
3. PythonAnywhere `Error log` 里的 SMTP 报错。
4. 邮件是否进了垃圾箱。
