#!/usr/bin/env python
#-*-coding:utf-8-*-

'fabfile module'

print('this import file__name__==',__name__)

__author__='chch'

import os
import sys
from imp import reload
import re
from datetime import datetime

from fabric.api import *

# env.user = 'ubuntu'
# env.sudo_user = 'root'
env.key_filename=['E:\\awskeyfile\\chch-ubun.pem']
env.hosts = ['ubuntu@ec2-35-162-188-57.us-west-2.compute.amazonaws.com']

db_user = 'www-data'
db_password = 'www-data'


def _now():
    return datetime.now().strftime('%y-%m-%d_%H.%M.%S')

def _current_path():   #pls run this file in its path
    return os.path.abspath('.')


# --------------------------------打包任务--------START
# 打包的目标文件名
_TAR_FILE = 'dist-awesome.tar.gz'

def build():
    includes = ['static', 'templates', 'favicon.ico', '*.py']
    excludes = ['test.*', '*.pyc', '*.pyo']
    
    # local来运行本地命令
    # 删除已存在的打包文件
    local('rm -f dist/%s' % _TAR_FILE)

    # with lcd(path) - 在本机,执行 cd path
    # os.path.abspath(path) - 取得当前路径的绝对路径
    # os.path.join(a, *p) - 将两部分路径整合到一起
    with lcd(os.path.join(_current_path(), 'www')):
        cmd = ['tar', '--dereference', '-czvf', '../dist/%s' % _TAR_FILE]
        cmd.extend(['--exclude=\'%s\'' % ex for ex in excludes])
        cmd.extend(includes)
        local(' '.join(cmd))
# --------------------------------打包任务--------END



# --------------------------------部署------------START
# 远程临时压缩包及位置
_REMOTE_TMP_TAR = '/tmp/%s' % _TAR_FILE

# 远程应用目录
_REMOTE_BASE_DIR = '/srv/awesome'

def deploy():
	# 用时间来命名新版本文件夹
    newdir = 'www-%s' % _now()
    # 删除已有的tar文件
    # run()函数的命令在服务器上运行,需要sudo权限时,用sudo()来代替run()
    run('rm -f %s' % _REMOTE_TMP_TAR)
    # 上传新的tar为文件, 前一个参数指定为本地文件,后一个指定为远程文件
    put('dist/%s' % _TAR_FILE, _REMOTE_TMP_TAR)
    # with cd(path) - 在远程计算机上,执行cd path
    # 当前在awesome/下
    # 创建新目录
    with cd(_REMOTE_BASE_DIR):
        sudo('mkdir %s' % newdir)
    with cd('%s/%s' % (_REMOTE_BASE_DIR, newdir)):
        sudo('tar -xzvf %s' % _REMOTE_TMP_TAR) # 解压到新目录
    # 重置软链接
    with cd(_REMOTE_BASE_DIR):
        sudo('rm -f www')
        sudo('ln -s %s www' % newdir)
        # chown将指定文件的拥有者改为指定的用户或组。系统管理员经常使用chown命令，在将文件拷贝到另一个用户的名录下之后，让用户拥有使用该文件的权限。 
        # -R 处理指定目录以及其子目录下的所有文件
        sudo('chown ubuntu:ubuntu www')
        sudo('chown -R ubuntu:ubuntu %s' % newdir)
    with cd('%s/%s'%(_REMOTE_BASE_DIR, 'www')):
        sudo('dos2unix app.py')
    # 重启python服务器和nginx服务器
    with settings(warn_only=True):
        sudo('supervisorctl stop awesome')
        sudo('supervisorctl start awesome')
        sudo('/etc/init.d/nginx reload')
# --------------------------------部署------------END



# ---------------------------------服务器上应用版本回退----------START
RE_FILES = re.compile('\r?\n')  # 用于ls 命令下分隔开各个文件
def rollback():
    with cd(_REMOTE_BASE_DIR):
        r = run('ls -p -1')  # 显示应用目录下的文件,并储存到变量r，文件夹后面带/
        # 取得版本的列表，去掉文件夹后面的/
        files = [s[:-1] for s in RE_FILES.split(r) if s.startswith('www-') and s.endswith('/')]
        # cmp参数指定比较函数,用匿名函数lambda表示,将按版本新旧排序
        # 对各版本进行排序
        files.sort(cmp=lambda s1, s2: 1 if s1 < s2 else -1)
        # 由于www通过软链接指向某一版本目录,因此ls -l将显示如下:
        # lrwxrwxrwx 1 root root 21 Dec  3 17:15 www -> www-16-12-03_17.15.49
        r = run('ls -l www')
        ss = r.split(' -> ')
        if len(ss) != 2:
            print ('ERROR: \'www\' is not a symbol link.')
            return
        current = ss[1]  # 取得当前版本号,赋给变量current
        print ('Found current symbol link points to: %s\n' % current)
        try:
            index = files.index(current)  # 找到当前在全部版本中的序号
        except ValueError, e:
            print ('ERROR: symbol link is invalid.')
            return
        if len(files) == index + 1:   # 序号是最末尾了,已经是最老的版本了
            print ('ERROR: already the oldest version.')
        old = files[index + 1]   # 取得当前版本上一版本号
        print ('==================================================')
        for f in files:    # 显示版次信息
            if f == current:
                print ('      Current ---> %s' % current)
            elif f == old:
                print ('  Rollback to ---> %s' % old)
            else:
                print ('                   %s' % f)
        print ('==================================================')
        print ('')
        sys.stdout.flush()
        yn = raw_input ('continue? y/N ')
        if yn != 'y' and yn != 'Y':
            print ('Rollback cancelled.')
            return
        print ('Start rollback...')
        sudo('rm -f www')
        sudo('ln -s %s www' % old)
        sudo('chown ubuntu:ubuntu www')
        with settings(warn_only=True):
            sudo('supervisorctl stop awesome')
            sudo('supervisorctl start awesome')
            sudo('/etc/init.d/nginx reload')
        print ('ROLLBACKED OK.')
# ---------------------------------服务器上应用版本回退---------END



# --------------------------------将服务器上的数据备份到本地-----START
def backup():
    dt = _now()
    f = 'backup-awesome-%s.sql' % dt  # 创建一个包含时间的db文件名
    with cd('/tmp'):
        # 将awesome的数据转出到f
        run('mysqldump --user=%s --password=%s --skip-opt --add-drop-table --default-character-set=utf8 --quick awesome > %s' % (db_user, db_password, f))
        run('tar -czvf %s.tar.gz %s' % (f, f))  # 将得到的数据打包
        get('%s.tar.gz' % f, '%s/backup/' % _current_path())   # 从服务器拉取数据包
        run('rm -f %s' % f)  # 删除数据文件与压缩包
        run('rm -f %s.tar.gz' % f)
# --------------------------------将服务器上的数据备份到本地-----END



# --------------------------------将服务器上数据回迁到本地-------START
def restore2local():
    '''
    Restore db to local
    '''
    backup_dir = os.path.join(_current_path(), 'backup')
    fs = os.listdir(backup_dir)  #备份目录下的文件列表
    # 取得本机已备份的数据库文件压缩包列表
    files = [f for f in fs if f.startswith('backup-') and f.endswith('.sql.tar.gz')]
    files.sort(cmp=lambda s1, s2: 1 if s1 < s2 else -1)  # 按时间从新到旧排序
    if len(files)==0:
        print 'No backup files found.'
        return
    print ('Found %s backup files:' % len(files))
    print ('==================================================')
    n = 0
    for f in files:  # 打印本机的备份数据信息
        print ('%s: %s' % (n, f))
        n = n + 1
    print ('==================================================')
    print ('')
    sys.stdout.flush()
    try:
        num = int(raw_input ('Restore file: '))
    except ValueError:
        print ('Invalid file number.')
        return
    if num>n-1 or num<0:
        print ('Invalid file number.')
        return
    restore_file = files[num]
    sys.stdout.flush()
    yn = raw_input('Restore file %s: %s? y/N ' % (num, restore_file))
    if yn != 'y' and yn != 'Y':
        print ('Restore cancelled.')
        return
    print ('Start restore to local database...')
    sys.stdout.flush()
    p = raw_input('Input mysql root password: ')
    sqls = [
        'drop database if exists awesome;',
        'create database awesome;',
        'grant select, insert, update, delete on awesome.* to \'%s\'@\'localhost\' identified by \'%s\';' % (db_user, db_password)
    ]
    for sql in sqls:
        local(r'mysql -uroot -p%s -e "%s"' % (p, sql))
    # 在本地应用备份目录下解压选择的数据库备份文件    
    with lcd(backup_dir):
        local('tar zxvf %s' % restore_file)
    # 将选择的备份恢复到本地数据库
    local(r'mysql -uroot -p%s --default-character-set=utf8 awesome < backup/%s' % (p, restore_file[:-7]))
    # 删除解压得到的备份文件,仅以压缩包形式储存
    with lcd(backup_dir):
        local('rm -f %s' % restore_file[:-7])
# --------------------------------将服务器上数据回迁到本地-------END
