#!/usr/bin/env python3
#-*-coding:utf-8-*-

'override configuration'

print('this import file__name__==',__name__)

__author__='chch'

import os
import sys
from imp import reload

#-----------start--------------

configs = {
 	# 重载的数据库信息,将会覆盖默认的数据库相关配置信息
	'db':{
		'host' : '127.0.0.1'
	}
}
