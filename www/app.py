#!/usr/bin/env python3
#-*-coding:utf-8-*-

'app.py for awesome-webapp'

print('this import file__name__==',__name__)

__author__='chch'

import os
import sys
from imp import reload
sys.path.append(r'c:/users/志冲/desktop/pytest')

#logging模块定义了一些函数和模块，可以帮助我们对一个应用程序或库实现一个灵活的事件日志处理系统
#logging模块可以纪录错误信息，并在错误信息记录完后继续执行
#debug()和info()方法没有显示任何信息,这是因为默认的日志级别是WARNING，所以低于此级别的日志不会记录
#日志级别大小关系为：CRITICAL > ERROR > WARNING > INFO > DEBUG > NOTSET
#通过basicConfig设置logging的默认level为INFO,修改日志记录等级要重启服务才有效

import logging;logging.basicConfig(level=logging.INFO)

# asyncio 内置了对异步IO的支持
# os模块提供了调用操作系统的接口函数
# json模块提供了Python对象到Json模块的转换
# time模块提供各种操作时间的函数
import asyncio,os,json,time

# datetime是处理日期和时间的标准库
from datetime import datetime

# aiohttp是基于asyncio实现的http框架
from aiohttp import web 

#先设置一个方法
def index(request):
	return web.Response(body=b'<h1>Awesome</h1>',content_type = 'text/html')

@asyncio.coroutine
def init (loop):
#创建一个web.app的实例， event loop used for processing HTTP requests.
#文档:If param is None asyncio.get_event_loop() used for getting default event loop, but we strongly recommend to use explicit loops everywhere.(所以传不传入loop都行)

	app = web.Application(loop=loop)
	app.router.add_route('GET','/',index)
#调用协程:创建一个TCP服务器,绑定到"127.0.0.1:9000"socket,并返回一个服务器对象
#用协程创建监听服务，其中loop为传入函数的协程，调用其类方法创建一个监听服务
#yield from 返回一个创建好的，绑定IP、端口、HTTP协议簇的监听服务的协程。yield from的作用是使srv的行为模式和 loop.create_server()一致
	srv = yield from loop.create_server(app.make_handler(),'127.0.0.1',9000)
	logging.info('server started at http://127.0.0.1:9000...')
	return srv


# asyncio的编程模块实际上就是一个消息循环。我们从asyncio模块中直接获取一个eventloop（事件循环）的引用，//
# 然后把需要执行的协程扔到eventloop中执行，就实现了异步IO
# 第一步是获取eventloop

# get_event_loop()函数详见python官方文档18.5.2.5
# get_event_loop() => 获取当前脚本下的事件循环，返回一个event loop对象(这个对象的类型是'asyncio.windows_events._WindowsSelectorEventLoop')，实现AbstractEventLoop（事件循环的基类）接口
# 如果当前脚本下没有事件循环，将抛出异常，get_event_loop()永远不会抛出None
loop = asyncio.get_event_loop()
loop.run_until_complete(init(loop))
loop.run_forever()
