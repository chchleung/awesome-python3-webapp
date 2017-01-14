#!/usr/bin/env python3
#-*-coding:utf-8-*-

'config default'

print('this import file__name__==',__name__)

__author__='chch'

import os
import sys
from imp import reload

#------------start---------

configs = {
	'debug': True,
	# 定义数据库相关信息
	'db':{
		'host':'127.0.0.1',
		'port':3306,
		'user':'www-data',
		'password':'www-data',
		'db':'awesome'
	},
	# 定义会话信息
	'session':{
		'secret': 'Awesome'
	}
}
