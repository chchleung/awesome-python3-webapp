#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__author__ = 'chch'

# functools高阶函数模块, 提供常用的高阶函数, 如wraps
# inspect the module provides several useful functions to help get informationabout live objects
import asyncio, os, inspect, logging, functools

# 从urllib导入解析模块
from urllib import parse

from aiohttp import web

 #导入自定义的api错误模块
from apis import APIError

# --------------定义装饰器----------------------Start
def get(path):
    '''
    Define decorator @get('/path')
    '''
    def decorator(func):
        # 该装饰器的作用是解决一些函数签名的问题
        # 比如若没有该装饰器,wrapper.__name__将为"wrapper"
        # 加了装饰器,wrapper.__name__就等于func.__name__
        @functools.wraps(func)
        def wrapper(*args, **kw):
            print('get 装饰器预先给fn添加了method和path信息')
            print('fn-method: ',wrapper.__method__)
            print('fn-route: ', wrapper.__route__)
            print('可看到此fn的装饰器预定义与request的形式吻合，于是调用fn')
            return func(*args, **kw)
        # 通过装饰器加上__method__属性,用于表示http method
        wrapper.__method__ = 'GET'
        # 通过装饰器加上__route__属性,用于表示path
        wrapper.__route__ = path
        return wrapper
    return decorator

def post(path):
    '''
    Define decorator @post('/path')
    '''
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kw):
            return func(*args, **kw)
        wrapper.__method__ = 'POST'
        wrapper.__route__ = path
        return wrapper
    return decorator

# -------------定义装饰器----------------------end


# -------------定义分析request参数情况的函数-------------start

# 获取函数的没有默认值的命名关键字的名称（require,即需要提供，没有默认值）
def get_required_kw_args(fn):
    args = []
    # signature.parameters属性,返回一个参数名的有序映射
    params = inspect.signature(fn).parameters
    for name, param in params.items():
         # 获取是命名关键字,且未指定默认值的参数名
        if param.kind == inspect.Parameter.KEYWORD_ONLY and param.default == inspect.Parameter.empty:
            args.append(name)
    return tuple(args)

# 获取命名关键字参数名，不论有否默认值
def get_named_kw_args(fn):
    args = []
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            args.append(name)
    return tuple(args)

#判断fn有没有命名关键字参数，有的话就返回True
def has_named_kw_args(fn):
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            return True

# 判断函数fn是否带有关键字参数（注意和命名关键字不一样）
def has_var_kw_arg(fn):
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        # VAR_KEYWORD, 表示关键字参数, 匹配**kw
        if param.kind == inspect.Parameter.VAR_KEYWORD:
            return True

# 判断fn的参数中有没有参数名为request的参数
def has_request_arg(fn):
    # 这里是把之前函数的一句语句拆分为两句，拆分原因是后面的raise要使用中间量sig---str(sig)
    sig = inspect.signature(fn)   #sig 是一个签名实例，通过str（）输出的话就是里面那堆参数，但其类型是signature
    params = sig.parameters       #paras 是将上面那堆参数变成一个orderDict, 类型是mappingproxy
    found = False
    for name, param in params.items():
        if name == 'request':
            found = True
            continue   # 如果找到，下面的代码不执行，直接进入下一个循环
        # 如果找到了request参数，又找到了其他参数是POSITIONAL_OR_KEYWORD（不是VAR_POSITIONAL可变参数、KEYWORD_ONLY命名关键字参数、VAR_KEYWORD关键字参数），则报错
        # request参数必须是最后一个位置参数（不论有没有默认值） 
        if found and (param.kind != inspect.Parameter.VAR_POSITIONAL and param.kind != inspect.Parameter.KEYWORD_ONLY and param.kind != inspect.Parameter.VAR_KEYWORD):
            raise ValueError('request parameter must be the last named parameter in function: %s%s' % (fn.__name__, str(sig)))
    return found

# -------------定义分析request参数情况的函数-------------end



# --------------------------------------封装urlhandler-----------------start

# 定义RequestHandler类,封装url处理函数
# RequestHandler的目的是从url函数中分析需要提取的参数,从request中获取必要的参数
# 调用url参数,将结果转换为web.response
class RequestHandler(object):

    def __init__(self, app, fn):
        self._app = app  # web application
        self._func = fn  # handler

        # 以下即为上面定义的一些判断函数与获取函数
        self._has_request_arg = has_request_arg(fn)       #有没有包含叫做‘request’的参数
        self._has_var_kw_arg = has_var_kw_arg(fn)         #有没有关键字参数
        self._has_named_kw_args = has_named_kw_args(fn)   #有没有命名关键字参数
        self._named_kw_args = get_named_kw_args(fn)       #获取命名关键字的各个参数的名称，不论有否默认值
        self._required_kw_args = get_required_kw_args(fn) #获取函数的没有默认值的命名关键字的名称

    # 定义了__call__,则其实例可以被视为函数
    # 此处参数为request
    async def __call__(self, request):
        logging.info('coroweb的RequestHanlder实例，接收到request,准备分析kw,然后传入fn处理')
        kw = None
        # 1, 如果存在关键字参数/命名关键字参数,分析method----------此处url处理函数存在3种参数情况：1. 只有*kw， 2. 只有**kw, 3. *kw + **kw
        if self._has_var_kw_arg or self._has_named_kw_args or self._required_kw_args:
            if request.method == 'POST':
                if not request.content_type:
                    return web.HTTPBadRequest('Missing Content-Type.')
                ct = request.content_type.lower()
                # application/json表示消息主体是序列化后的json字符串
                if ct.startswith('application/json'):
                    # request.json方法的作用是读取request body, 并以json格式解码
                    params = await request.json()
                    if not isinstance(params, dict):
                        return web.HTTPBadRequest('JSON body must be object.')
                    kw = params
                # 以下2种content type都表示消息主体是表单
                elif ct.startswith('application/x-www-form-urlencoded') or ct.startswith('multipart/form-data'):
                    # request.post方法从request body读取POST参数,即表单信息,并包装成字典赋给kw变量
                    params = await request.post()
                    kw = dict(**params)
                # 此处我们只处理以上三种post 提交数据方式    
                else:
                    return web.HTTPBadRequest('Unsupported Content-Type: %s' % request.content_type)
            
            if request.method == 'GET':
                # request.query_string表示url中的查询字符串
                # Request.QueryString（取得地址栏参数值）获取地址栏中的参数，意思就是取得”？"号后面的参数值．如果是多个是用这”＆”符号连接起来的．
                # 比如我百度ReedSun，得到网址为https://www.baidu.com/s?ie=UTF-8&wd=ReedSun
                # 其中‘ie=UTF-8&wd=ReedSun’就是查询字符串
                qs = request.query_string
                if qs:
                    kw = dict()
                    # parse.parse_qs(qs, keep_blank_values=False, strict_parsing=False)函数的作用是解析一个给定的字符串
                    # keep_blank_values默认为False，指示是否忽略空白值，True不忽略，False忽略
                    # strict_parsing如果是True，遇到错误是会抛出ValueError错误，如果是False会忽略错误
                    # 这个函数将返回一个字典，其中key是等号之前的字符串，value是等号之后的字符串但会是列表
                    # 比如上面的例子就会返回{'ie': ['UTF-8'], 'wd': ['ReedSun']}
                    for k, v in parse.parse_qs(qs, True).items():
                        kw[k] = v[0]

        # 2, 经过以上如果为空，则拿到match_info
        if kw is None:
            # 经过以上处理, kw仍为空,即以上全部不匹配,则获取请求的abstract math info(抽象数学信息)
            # match_info主要是保存像@get('/blog/{id}')里面的id，就是路由路径里的参数
            kw = dict(**request.match_info)

        # 3， 当kw不为空：    上面是3种情况：1. 只有*kw， 2. 只有**kw, 3. *kw + **kw
        else:
             # 3-1如果fn没有可变的关键字参数，但是有关键字参数， 即第一种情况，只有*kw，则更新一下kw
            if not self._has_var_kw_arg and self._named_kw_args:
                # 下面五行代码的意思是将kw中key为关键字参数的项提取出来保存为新的kw
                # 即剔除kw中key不是fn的关键字参数的项
                # remove all unamed kw:
                copy = dict()
                for name in self._named_kw_args:
                    if name in kw:
                        copy[name] = kw[name]
                # 用math_info的值覆盖kw中的原值
                kw = copy

            # 3-2 不论上述3种的哪种情况，都看一下match_info，并以match_info的值为准
            # 遍历request.match_info(abstract math info), 若其key又存在于kw中,发出重复参数警告
            # check named arg:
            for k, v in request.match_info.items():
                if k in kw:
                    logging.warning('Duplicate arg name in named arg and kw args: %s' % k)
                kw[k] = v

        # 4， 如果有request参数，就把这个参数存入kw
        if self._has_request_arg:
            kw['request'] = request

        # 5，  若存在未指定值的命名关键字参数,且参数名未在kw中,返回丢失参数信息    
        # check required kw:
        if self._required_kw_args:
            for name in self._required_kw_args:
                if not name in kw:
                    return web.HTTPBadRequest('Missing argument: %s' % name)
       
        #---------以上过程即为根据url处理函数的参数定义， 从request中获得必要的参数，并组成kw--------

        # 调用handler（url处理函数）处理，并返回response
        logging.info('coroweb模块：根据fn获取request的kw完毕，准备调用fn--call with args: %s' % str(kw))

        try:
            r = await self._func(**kw)
            return r
        except APIError as e:
            return dict(error=e.error, data=e.data, message=e.message)

#-------------------完成requestHandler的封装---------end




# -----------------注册各种handler------------------start


def add_static(app):
    # os.path.abspath(__file__), 返回当前脚本的绝对路径(包括文件名)
    # os.path.dirname(), 去掉文件名,返回目录路径
    # os.path.join(), 将分离的各部分组合成一个路径名
    # 因此以下操作就是将本文件同目录下的static目录(即www/static/)加入到应用的路由管理器中
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
    # app = web.Application(loop=loop)这是在app.py模块中定义的
    app.router.add_static('/static/', path)
    logging.info('coroweb模块--加载静态文件：add static %s => %s' % ('/static/', path))


# 把单个url处理函数(fn)注册到app, fn通过装饰器里面多了method和path/route信息，从而可以用aiohttp的注册方式注册到app
def add_route(app, fn):
    method = getattr(fn, '__method__', None)
    path = getattr(fn, '__route__', None)
    if path is None or method is None:
        raise ValueError('@get or @post not defined in %s.' % str(fn))
    # 如果函数fn是不是一个协程或者生成器，就把这个函数变成协程
    if not asyncio.iscoroutinefunction(fn) and not inspect.isgeneratorfunction(fn):
        fn = asyncio.coroutine(fn)
    logging.info('coroweb模块--注册handler：add route %s %s => %s(%s)' % (method, path, fn.__name__, ', '.join(inspect.signature(fn).parameters.keys())))
    app.router.add_route(method, path, RequestHandler(app, fn)) #因为调用的是handler,所以传入类实例。但需要一开始的path和method信息，所以只传入url处理函数fn，到最后注册才将其传入RequestHandler
    # 根据文档: A request handler can be any callable that accepts a Request instance as its only argument and returns a StreamResponse derived (e.g. Response) instance: 注册函数里面的第三个参数handler可以call而且只能接受一个参数request，所以我们人为地创造RequestHandler并且call的时候只能接受一个request参数，但貌似初始化时候的app参数一直也用不上？


# 将handlers模块中所有请求处理函数提取出来交给add_route自动去处理
def add_routes(app, module_name):
    # 如果handlers模块在当前目录下，传入的module_name就是handlers
    # 如果handlers模块在handler目录下, 传入的module_name就是handler.handlers

    # Python rfind() 返回字符串最后一次出现的位置，如果没有匹配项则返回-1。
    # str.rfind(str, beg=0 end=len(string))
    # str -- 查找的字符串
    # beg -- 开始查找的位置，默认为0
    # end -- 结束查找位置，默认为字符串的长度。
    # 返回字符串最后一次出现的位置(索引数），如果没有匹配项则返回-1。
    n = module_name.rfind('.')
    # -1 表示未找到,即module_name表示的模块直接在当前目录导入
    if n == (-1):
        # __import__(module_name[, globals[, locals[, fromlist]]]) 
        # 可选参数默认为globals(),locals(),[]
        # 举个例子，__import__('os',globals(),locals(),['path','pip'])  #等价于from os import path, pip  
        # ----- 此时，mod:  <module 'hello' from 'C:\\Users\\志冲\\desktop\\hello.py'>  
        # 听说有黑魔法： mod = __import__(module_name, fromlist=[''])
        mod = __import__(module_name, globals(), locals())

    else:
        # 当module_name为handler.handlers时，[n+1:]就是取.后面的部分，也就是handlers
        name = module_name[n+1:]
        # 下面的语句相当于执行了两个步骤，传入的module_name是aaa.bbb，第一个步骤相当于
        # 第一个步骤相当于from aaa import bbb导入模块以及子模块
        # 第二个步骤通过getattr()方法取得子模块名, 如datetime.datetime
        # ------此时，里面的__import__效果为：<module 'pytest' (namespace)> , 但貌似里面的[name]加不加效果都是一样
        # ------然后，外面的getattr(XX,name)效果为：<module 'pytest.webtest' from 'C:\\Users\\志冲\\desktop\\pytest\\webtest.py'>
        # 即最后还是要拿到module XX from XXX\\X.py 的效果
        mod = getattr(__import__(module_name[:n], globals(), locals(), [name]), name)

    # dir()不带参数时，返回当前范围内的变量、方法和定义的类型列表；带参数时，返回参数的属性、方法列表。如果参数包含方法__dir__()，该方法将被调用。如果参数不包含__dir__()，该方法将最大限度地收集参数信息。
    for attr in dir(mod):
        # 忽略以_开头的属性与方法,_xx或__xx(前导1/2个下划线)指示方法或属性为私有的,__xx__指示为特殊变量
        # 私有的,能引用(python并不存在真正私有),但不应引用;特殊的,可以直接应用,但一般有特殊用途
        if attr.startswith('_'):
            continue
        # 排除私有属性后，就把属性提取出来  
        # attr是dir这个属性数组里面的一个元素，是个str，所以根据这个str，在mod里面拿到这个属性对象fn
        fn = getattr(mod, attr)
        # 查看提取出来的属性是不是函数(但是能call不一定是function，也可以是实例，所以写handlers模块的时候要注意模块里面的属性和函数，不是function的要处理一下。或者这里可以检查是不是函数)
        # 例如：if isinstance(fn,types.FunctionType):
        if callable(fn):  
            method = getattr(fn, '__method__', None)
            path = getattr(fn, '__route__', None)
            # 如果是函数，再判断是否有__method__和__route__属性，如果存在则使用app_route函数注册
            if method and path:
                add_route(app, fn)

#----------------注册各种hander-----------------------end






# RequestHandler也可以把任何参数都变成self._func(**kw)的形式。那问题来了，那kw的参数到底要去哪里去获取呢？
# request.match_info的参数： match_info主要是保存像@get('/blog/{id}')里面的id，就是路由路径里的参数
# GET的参数： 像例如/?page=2
# POST的参数： api的json或者是网页中from
# request参数： 有时需要验证用户信息就需要获取request里面的数据