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

# Jinja2 是仿照 Django 模板的 Python 前端引擎模板
# Environment指的是jinjia2模板的配置环境，FileSystemLoader是文件系统加载器，用来加载模板路径
from jinja2 import Environment, FileSystemLoader

import orm

from coroweb import add_routes,add_static

# 加载解密从客户端获取的cookie的方式以及服务器设置的cookie名称
from handlers import cookie2user, COOKIE_NAME  


# 这个函数的功能是初始化jinja2模板，配置jinja2的环境-------------------start
def init_jinja2(app,**kw):
	logging.info('app模块------init jinja2...')
	options = dict(
		autoescape=kw.get('autoescape',True), # 自动转义xml/html的特殊字符
		block_start_string = kw.get('block_start_string','{%'),       # 设置代码起始字符串
		block_end_string = kw.get('block_end_string','%}'),           # 设置代码的终止字符串
		variable_start_string = kw.get('variable_start_string','{{'), # 这两句分别设置了变量的起始和结束字符串
		variable_end_string = kw.get('variable_end_string','}}'),     # 就是说{{和}}中间是变量
		auto_reload = kw.get('auto_reload',True)                      # 每当对模板发起请求,加载器首先检查模板是否发生改变.若是,则重载模板
	)

	path = kw.get('path',None)  # 从kw中获取模板路径，如果没有传入这个参数则默认为None
	# 如果path为None，则将当前文件所在目录下的templates目录设为模板文件目录
	if path is None:
		# os.path.abspath(__file__)取当前文件的绝对目录
        # os.path.dirname()取绝对目录的路径部分
        # os.path.join(path， name)把目录和名字组合
		path = os.path.join(os.path.dirname(os.path.abspath(__file__)),'templates')
	logging.info('app模块------set jinja2 template path: %s' % path)
	 # 初始化jinja2环境。
	 # loader=FileSystemLoader(path)指的是到哪个目录下加载模板文件， **options就是前面的options
	env = Environment(loader = FileSystemLoader(path),**options)
	filters = kw.get('filters',None)
	if filters is not None:
		for name,f in filters.items():
			env.filters[name] = f   # 如果有filters参数，则在env中添加过滤器
	# 将jinja环境赋给app的__templating__属性
	# 前面已经把jinjia2的环境配置都赋值给env了，这里再把env存入app的dict中，这样app就知道要去哪找模板，怎么解析模板
	app['__templating__'] = env


# 时间过滤器，作用是返回日志创建的时间，用于显示在日志标题下面
def datetime_filter(t):
	# 定义时间差
    delta = int(time.time() - t)
    # 针对时间分类
    if delta < 60:
        return u'1分钟前'
    if delta < 3600:
        return u'%s分钟前' % (delta // 60)
    if delta < 86400:
        return u'%s小时前' % (delta // 3600)
    if delta < 604800:
        return u'%s天前' % (delta // 86400)
    #如果10天以前就按年月日返回
    dt = datetime.fromtimestamp(t)
    return u'%s年%s月%s日' % (dt.year, dt.month, dt.day)


# 为jinja2作准备--------------------------------------------------------------end



# 准备middleware拦截器--------------------------------------------------------strat

# 这个函数的作用就是当http请求的时候，通过logging.info输出请求的信息，其中包括请求的方法和路径
async def logger_factory(app,handler):
	async def logger(request):
		print('\n通过logger_factory，我们看看request是什么：', str(request))
		logging.info('app模块的logger_factory,单纯的log一下request的路径和方法，然后准备继续将request传入RequestHandler处理---Request: %s %s' %(request.method,request.path))
		return (await handler(request))  # 日志记录完毕之后, 调用传入的handler继续处理请求
	return logger


# 在处理请求之前,先将cookie解析出来,并将登录用户绑定到request对象上
# 这样后续的url处理函数就可以直接拿到登录用户
# 以后的每个请求,都是在这个middle之后处理的,都已经绑定了用户信息
async def auth_factory(app, handler):
    async def auth(request):
        logging.info('app模块的auth_factory : 准备通过cookie check user, method and path is: %s %s' % (request.method, request.path))
        request.__user__ = None  #给 request增加一个参数__user__, 可以看到之后的request都会带着__user__参数，说明request从头到尾都是指向同一个对象，并可以修改
        cookie_str = request.cookies.get(COOKIE_NAME)   #request有一个叫cookie的属性，是个dict, key是我们之前set的名称，这里的COOKIE_NAME就是我们在handlers.py设定的awesession, 通过get(COOKIE_NAME)获得键值，就是我们user2cookie所输出的字符串（uid-exp-pw3）

        if not cookie_str:
            logging.info('app模块的auth_factory : 没有cookie信息')
        if cookie_str:
            user = await cookie2user(cookie_str)  # 根据函数看是否符合，符合返回一个user对象，不符合返回None
            if user:
                logging.info('app模块的auth_factory: cookie验证成功，将user对象放到request的__user__属性内。set current user: %s' % user.email)
                request.__user__ = user  # 这样新输入的__user__属性就有了内容，是个user对象
            else:
                logging.info('app模块的auth_factory: cookie验证失败')

        # 如果请求路径是管理页面，但是用户不是管理员，将重定向到登陆页面
        if request.path.startswith('/manage/') and (request.__user__ is None or not request.__user__.admin):
            return web.HTTPFound('/signin')
        
        return (await handler(request))
    return auth


# 只有当请求方法为POST时这个函数才起作用
async def data_factory(app,handler):
	async def parse_data(request):
		if request.method == 'POST':
			if request.content_type.startswith('application/json'):
				request.__data__ = await request.json() # request.json方法,读取消息主题,并以utf-8解码，将消息主体存入请求的__data__属性
				logging.info('request json: %s' % str(request.__data__))
			elif request.content_type.startswith('application/x-www-form-urlencoded'):
				request.__data__ = await request.post()
				logging.info('request form : %s' %str(request.__data__))
		return (await handler(request))
	return parse_data


# 上面2个middle factory是在url处理函数之前先对请求进行了处理,以下则在url处理函数之后进行处理
# 其将request handler的返回值转换为web.Response对象
async def response_factory(app, handler):
    async def response(request):
        logging.info('app模块的response_factory,异步等待接收handler传过来的东西-----Response handler...')
        r = await handler(request)

        logging.info('app模块response_factory，接收到handler传过来的原始response，规范成webResponse形式...')
        logging.info('app模块response_factory，看看返回的类型： %s' %type(r))

        # 若响应结果为StreamResponse,直接返回
        # StreamResponse是aiohttp定义response的基类,即所有响应类型都继承自该类
        # StreamResponse主要为流式数据而设计
        if isinstance(r, web.StreamResponse):
            logging.info('app模块response_factory，这是个web.StreamResponse类型的返回，所以直接返回')
            return r
         # 若响应结果为字节流,则将其作为应答的body部分,并设置响应类型为流型
        if isinstance(r, bytes):
            resp = web.Response(body=r)
            resp.content_type = 'application/octet-stream'
            return resp
         # 若响应结果为字符串
        if isinstance(r, str):
        	# 判断响应结果是否为重定向.若是,则返回重定向的地址
            if r.startswith('redirect:'):
                return web.HTTPFound(r[9:])
             # 响应结果不是重定向,则以utf-8对字符串进行编码,作为body.设置相应的响应类型
            resp = web.Response(body=r.encode('utf-8'))
            resp.content_type = 'text/html;charset=utf-8'
            return resp
        # 若响应结果为字典,则获取它的模板属性,此处为jinja2.env(见init_jinja2)
        if isinstance(r, dict):
            template = r.get('__template__')
            # 若不存在对应模板,则将字典调整为json格式返回,并设置响应类型为json 
            if template is None:
                resp = web.Response(body=json.dumps(r, ensure_ascii=False, default=lambda o: o.__dict__).encode('utf-8'))
                resp.content_type = 'application/json;charset=utf-8'
                return resp
             # 存在对应模板的,则将套用模板,用request handler的结果进行渲染
            else:
                resp = web.Response(body=app['__templating__'].get_template(template).render(**r).encode('utf-8'))
                resp.content_type = 'text/html;charset=utf-8'
                return resp
        # 若响应结果为整型的
        # 此时r为状态码,即404,500等
        if isinstance(r, int) and r >= 100 and r < 600:
            return web.Response(r)
        # 若响应结果为元组,并且长度为2
        if isinstance(r, tuple) and len(r) == 2:
            t, m = r
            # t为http状态码,m为错误描述
            # 判断t是否满足100~600的条件
            if isinstance(t, int) and t >= 100 and t < 600:
                return web.Response(t, str(m))
        # default:
        # 默认以字符串形式返回响应结果,设置类型为普通文本
        resp = web.Response(body=str(r).encode('utf-8'))
        resp.content_type = 'text/plain;charset=utf-8'
        return resp
    return response

# 准备middleware拦截器--------------------------------------------------------end






# #单例测试首页用：先设置一个方法
# def index(request):
# 	return web.Response(body=b'<h1>Awesome</h1>',content_type = 'text/html')









#------------------------------初始化服务器-----------------------------start-----------------------

@asyncio.coroutine
def init (loop):
	# 创建数据库连接池
	yield from orm.create_pool(loop = loop, host = '127.0.0.1', port = 3306, user = 'www-data', password = 'www-data', db = 'awesome')

	# 创建一个web.app的实例， event loop used for processing HTTP request.
	# 文档:If param is None asyncio.get_event_loop() used for getting default event loop, but we strongly recommend to use explicit loops everywhere.(所以传不传入loop都行)
	app = web.Application(loop=loop,middlewares=[logger_factory, auth_factory, response_factory])
	
	# 设置模板为jiaja2, 并以时间为过滤器
	init_jinja2(app,filters = dict(datetime = datetime_filter))
	
	# 注册所有url处理函数
    #调用coroweb的注册函数，传入模版的名称/地址，从而逐个注册handler模版里面的每一个url
	add_routes(app,'handlers')
	
	# 将当前目录下的static目录装入app目录
	add_static(app)

	# app.router.add_route('GET','/',index) # 测试首页用

	# 调用协程:创建一个TCP服务器,绑定到"127.0.0.1:9000"socket,并返回一个服务器对象
	# 用协程创建监听服务，其中loop为传入函数的协程，调用其类方法创建一个监听服务
	# yield from 返回一个创建好的，绑定IP、端口、HTTP协议簇的监听服务的协程。yield from的作用是使srv的行为模式和 loop.create_server()一致
	srv = yield from loop.create_server(app.make_handler(),'127.0.0.1',9001)
	logging.info('app模块------服务启动-------server started at http://127.0.0.1:9000...')
	logging.info('***********************************************\n\n')

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


#------------------------------初始化服务器-----------------------------end-----------------------