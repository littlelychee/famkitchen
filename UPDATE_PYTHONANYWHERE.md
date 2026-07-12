# FamKitchen 更新到 PythonAnywhere 流程

这份文档用于每次本地改完代码后，把最新版本同步到线上。

## 1. 本地确认改动

在本地项目目录执行：

```bash
cd /Users/zepeng/zepeng/famkitchen
git status
```

如果看到改动文件，先本地检查：

```bash
.venv/bin/python manage.py check
```

## 2. 本地提交并推送到 GitHub

```bash
git add .
git commit -m "Update FamKitchen"
git push
```

如果 `git status` 显示没有需要提交的内容，就不需要 commit，直接去 PythonAnywhere 拉取即可。

## 3. PythonAnywhere 拉取最新代码

打开 PythonAnywhere 的 Bash console：

```bash
cd ~/famkitchen
source .venv/bin/activate
git pull
```

## 4. 更新依赖和数据库

如果 `requirements.txt` 没变，`pip install` 这一步通常不会有实际变化，但保留执行最省心：

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
```

## 5. 重启线上应用

回到 PythonAnywhere 的 `Web` 页面，点击：

```text
Reload
```

然后打开线上地址检查：

```text
https://zepeng.pythonanywhere.com
```

## 6. 如果这次更新涉及线上数据

线上真实数据在 PythonAnywhere 里，不在 GitHub 里：

```text
/home/zepeng/famkitchen/db.sqlite3
/home/zepeng/famkitchen/media/
```

如果要改数据库结构，`python manage.py migrate` 前可以先备份：

```bash
cd ~/famkitchen
mkdir -p backups
cp db.sqlite3 backups/db.sqlite3.$(date +%Y%m%d-%H%M%S)
tar -czf backups/media.$(date +%Y%m%d-%H%M%S).tar.gz media
```

不要用本地 `db.sqlite3` 或本地 `media/` 直接覆盖线上，除非你明确想把线上数据替换成本地测试数据。
