#!/usr/bin/env python3
#-*-coding:utf-8-*-

'test for day4'

print('this import file__name__==',__name__)

__author__='chch'

import os
import sys
from imp import reload


# --------------start-----------------------

import asyncio
import orm
from models import User,Blog,Comment

@asyncio.coroutine
def test():
	#连接数据库
	yield from orm.create_pool(loop=loop,user='www-data',password='www-data',db='awesome')

	#将旧内容拿出来
	old=yield from User.findAll(where='`passwd` = ?',args='1234567890',orderBy='`name` DESC') #后面不跟或跟ASC则为升序，跟DESC则为降序
	
	#尝试更新后，删掉旧数据
	for k in old:
		k.passwd='000'
		yield from k.update()
		
		yield from k.remove()

	#测试建立新数据
	for i in range(1,4):
		u = User(name='Test%d'%i,email = 'test%d@example.com'%i,passwd = '1234567890',image='about=blank')
		yield from u.save()

	#findNumber的函数貌似不太对，如果用select count(*) 估计才是想要的效果
	b=yield from User.findNumber('name')
	print('findNumber is :',b)

if __name__=='__main__':
	loop = asyncio.get_event_loop()
	loop.run_until_complete(test())
	
	# 如果test出现event loop is close 有2方法，一个是下面2行close pool,一个是在orm里面的execute加一个 close connect，但不认可close connect的效率
	#可以在orm设置多一个销毁函数，使用完的时候调用。看文档close应该放在协程里面最后进行，而不是放在外面最后来关闭。
	#@asyncio.coroutine
	#def destory_pool(): #销毁连接池
	#	global __pool
	#	if __pool is not None:
	#   __pool.close()
	#   yield from  __pool.wait_closed()
	#其实效果跟下面两句一样    

	orm.__pool.close()
	loop.run_until_complete(orm.__pool.wait_closed())

	loop.close()
	if loop.is_closed():
		sys.exit(0)