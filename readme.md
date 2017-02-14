##This is a python project for webapp.##

**感谢廖大的教程。**

###准备工作：###
- python3.5 及以上版本
- aiohttp: 异步http服务器
- jinja2: python的模板渲染引擎
- aiomysql: 异步mysql库,参考资料

###代码结构：###
www  
 +- static:存放静态资源  
 +- templates:存放模板文件  
 -  app.py: HTTP服务器以及处理HTTP请求；拦截器、jinja2模板、URL处理函数注册等  
 -  orm.py: ORM框架  
 -  coroweb.py: 封装aiohttp，即写个装饰器更好的从Request对象获取参数和返回Response对象  
 -  apis.py: 定义几个错误异常类和Page类用于分页  
 -  config_default.py:默认的配置文件信息  
 -  config_override.py:自定义的配置文件信息  
 -  config.py:默认和自定义配置文件合并  
 -  markdown2.py:支持markdown显示的插件  
 -  pymonnitor.py: 用于支持自动检测代码改动重启服务  

*其中重要的模块有三个：orm.py、coroweb.py、app.py，下面将分别介绍。*

#### orm.py实现思路： ####
ORM全称为对象关系映射(Object Relation Mapping)，即用一个类来对应数据库中的一个表，一个对象来对应数据库中的一行，表现在代码中，即用类属性来对应一个表，用实例属性来对应数据库中的一行。

具体步骤如下：

1. 实现元类ModelMetaclass：创建一些特殊的类属性，用来完成类属性和表的映射关系，并定义一些默认的SQL语句
2. 实现Model类：包含基本的get,set方法用于获取和设置实例属性的值，并实现相应的SQL处理函数
3. 实现三个映射数据库表的类：User、Blog、Comment，在应用层用户只要使用这三个类即可

####web框架实现思路：####

web框架在此处主要用于对aiohttp库做更高层次的封装，从简单的WSGI接口到一个复杂的web framework，本质上还是对request请求对象和response响应对象的处理，可以将这个过程想象成工厂中的一条流水线生产产品，request对象就是流水线的原料，这个原料在经过一系列的加工后，生成一个response对象返回给浏览器。

过程如下：

- app.py中注册所有处理函数、初始化jinja2、添加静态文件路径
- 创建服务器监听线程
- 监听线程收到一个request请求
- 经过拦截器(middlewares)的处理
- 调用RequestHandler实例中的call方法；再调用call方法中的post或者get方法
- 调用响应的URL处理函数，并返回结果
- response_factory在拿到经URL处理函数返回过来的对象，经过一系列类型判断后，构造出正确web.Response对象，返回给客户端