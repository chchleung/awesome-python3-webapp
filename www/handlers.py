#!/usr/bin/env python3
#-*-coding:utf-8-*-

'url handlers'

print('this import file__name__==',__name__)

__author__='chch'

import re,time,json,logging,hashlib,base64,asyncio

from coroweb import get, post

from models import User, Comment, Blog, next_id

from apis import APIError,APIValueError,APIResourceNotFoundError,APIPermissionError,Page

from config import configs

from aiohttp import web

import markdown2


# befort day 7------------------------------------------------------------------------START
# @get('/')
# async def index(request):
# 	logging.info('调用handler模块的index函数，读取了数据库，返回指定template和users')
# 	users = await User.findAll()
# 	return {
# 		'__template__':'test.html',
# 		'users':users
# 	}
# befort day 7--------------------------------------------------------------------------END



# 用于将str转成int来传回页码
def get_page_index(page_str):
	p  = 1
	try:
		p = int(page_str)
	except ValueError as e:
		pass
	if p < 1:
		p = 1
	return p


# -----------------------------检查是否管理员-----------------------------------------START
def check_admin(request):
    if request.__user__ is None or not request.__user__.admin:
        raise APIPermissionError()
    logging.info('handlers模块，check_admin, 验证管理员成功')
# -----------------------------检查是否管理员-----------------------------------------END



COOKIE_NAME = 'awesession'
_COOKIE_KEY = configs.session.secret

#-------------------------计算加密cookie----------------------------------------------START
def user2cookie(user, max_age):
    '''
    Generate cookie str by user.
    '''
    # build cookie string by: id-expires-sha1
    # expires(失效时间)是当前时间加上cookie最大存活时间的字符串
    expires = str(int(time.time() + max_age)) 
    
    # 利用用户id,加密后的密码,失效时间,加上cookie密钥,组合成待加密的原始字符串
    # 这里的passwd(pw-2)其实是客户输入的(pw-0)经过客户端装配上email加密的sha1(pw-1)，再在服务器装配上uid加密的sha1(pw-2), 是存到数据库的真实内容(pw-2)
    s = '%s-%s-%s-%s' % (user.id, user.passwd, expires, _COOKIE_KEY)  # 我们把这个4合一再加密的叫做 pw-3

    # 生成加密的字符串,并与用户id,失效时间共同组成cookie
    L = [user.id, expires, hashlib.sha1(s.encode('utf-8')).hexdigest()]
    return '-'.join(L)                  # 返回的是从list转换过来的一个字符串，会作为cookie的一个参数,配合名称、时效等其他参数来组装cookie
#-------------------------计算加密cookie----------------------------------------------END


#-------------------------解密cookie--------------------------------------------------START
@asyncio.coroutine
def cookie2user(cookie_str):   #用在了app模块的auth拦截器
    '''
    Parse cookie and load user if cookie is valid.
    '''
    # cookie_str就是user2cookie函数的返回值
    if not cookie_str:
        return None
    try:
    	# 解密是加密的逆向过程,因此,先通过'-'拆分cookie,得到用户id,失效时间,以及加密字符串
        L = cookie_str.split('-')
        if len(L) != 3:                  # 由上可知,cookie由3部分组成,若拆分得到不是3部分,显然出错
            return None
        uid, expires, sha1 = L
        if int(expires) < time.time():   # 时间是浮点表示的时间戳,一直在增大.因此失效时间小于当前时间,说明cookie已失效
            return None
        user = yield from User.find(uid) # 在拆分得到的id在数据库中查找用户信息
        if user is None:
            return None
        # 利用用户id,数据库存储的密码pw-2,失效时间,加上cookie密钥,组合成待加密的原始字符串
        # 重复u2c的加密方法，对其进行加密,与从cookie分解得到的sha1进行比较.若相等,则该cookie合法
        s = '%s-%s-%s-%s' % (uid, user.passwd, expires, _COOKIE_KEY)   # 根据数据库的资料，组成pw-3
        if sha1 != hashlib.sha1(s.encode('utf-8')).hexdigest():
            logging.info('invalid sha1')
            return None
        # 验证cookie,就是为了验证当前用户是否仍登录着,从而使用户不必重新登录，因此,返回用户信息即可
        user.passwd = '******'
        return user
    except Exception as e:
        logging.exception(e)
        return None
#-------------------------解密cookie--------------------------------------------------END



#---------------------------------------首页------------------------------------------START
@get('/')
def index(request,*, page='1'):  
    # summary = 'Lorem ipsum dolor sit amet, consectetur adipisicing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.'#Lorem ipsum
    # 是指一篇常用于排版设计领域的拉丁文文章，主要的目的为测试文章或文字在不同字型、版型下看起来的效果
    # blogs = [
    #     Blog(id='1', name='Test Blog', summary=summary, created_at=time.time()-120),
    #     Blog(id='2', name='Something New', summary=summary, created_at=time.time()-3600),
    #     Blog(id='3', name='Learn Swift', summary=summary, created_at=time.time()-7200),
    #     Blog(id='4', name = 'One another', summary = summary, created_at = time.time()-608402)
    # ]
    page_index = get_page_index(page)
    num = yield from Blog.findNumber('count(id)')
    page_obj = Page(num,page_index)
    if num == 0:
        blogs=[]
    else:
        blogs = yield from Blog.findAll(orderBy='created_at desc',limit=(page_obj.offset,page_obj.limit))
    return {
        '__template__': 'home_blogs.html',
        'blogs': blogs,
        'page_obj':page_obj,
        '__user__':request.__user__
    }
#---------------------------------------首页--------------------------------------------END



#-------------------------------注册--------------------------------------------------START
@get('/register')
def register(request):
    have_signin=None
    if not request.__user__== None:
        have_signin = request.__user__
        have_signin.name = '登录了还注册个啥'
    return {
        '__template__': 'register.html',
        '__user__': have_signin
    }


_RE_EMAIL = re.compile(r'^[a-z0-9\.\-\_]+\@[a-z0-9\-\_]+(\.[a-z0-9\-\_]+){1,4}$')
_RE_SHA1 = re.compile(r'^[0-9a-f]{40}$')

@post('/api/reg_users')
def api_register_user(*, email, name, passwd):   # 这个passwd已经是经过客户端装载了email的加密的pw-1
    if not name or not name.strip():             # strip() 方法用于移除字符串头尾指定的字符（默认为空格）
        raise APIValueError('name')
    if not email or not _RE_EMAIL.match(email):
        raise APIValueError('email')
    if not passwd or not _RE_SHA1.match(passwd):
        raise APIValueError('passwd')
    users = yield from User.findAll('email=?', [email]) #findAll的args总是应该加个括号
    if len(users) > 0:
        raise APIError('register:failed', 'email', 'Email is already in use.')
    uid = next_id()	
    sha1_passwd = '%s:%s' % (uid, passwd)  # 存入数据库的是装载uid后加密的pw-2
    # unicode对象在进行哈希运算之前必须先编码。hexdigest()函数将hash对象转换成16进制表示的字符串
    # Gravatar(Globally Recognized Avatar)是一项用于提供在全球范围内使用的头像服务。只要在Gravatar的服务器上上传了你自己的头像，便可以在其他任何支持Gravatar的博客、论坛等地方使用它。此处image就是一个根据用户email生成的头像
    user = User(id=uid, name=name.strip(), email=email, passwd=hashlib.sha1(sha1_passwd.encode('utf-8')).hexdigest(), image='http://www.gravatar.com/avatar/%s?d=mm&s=120' % hashlib.md5(email.encode('utf-8')).hexdigest())
    yield from user.save()
   
    # make session cookie， 返回带有cookie的response
    # http协议是一种无状态的协议,即服务器并不知道用户上一次做了什么.
    # 因此服务器可以通过设置或读取Cookies中包含信息,借此维护用户跟服务器会话中的状态
    r = web.Response()
    r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)  # 第二个参数是一个字符串，用于校验。 86400代表24小时
    user.passwd = '******'  # 保证真实的密码不会因返回而暴漏
    r.content_type = 'application/json'   # 设置content_type,将在data_factory中间件中继续处理
    r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')     # json.dumps方法将对象序列化为json格式
    return r
#-------------------------------注册-------------------------------------------------END



#-------------------------------登录------------------------------------------------START
@get('/signin')
def signin():
    return {
        '__template__': 'signin.html'
    }

@post('/api/authenticate')         # 因为有auth_factory拦截器的原因，传入的request会先验证一次cookie，说明是不是用户。无论是否，这里登录又会再验证一次
def authenticate(*, email, passwd):
    if not email:
        raise APIValueError('email', 'Invalid email.')
    if not passwd:											# 传入的passwd 是 pw-1
        raise APIValueError('passwd', 'Invalid password.')
    users = yield from User.findAll('email=?', [email])   # 从数据库获取对应email的信息
    if len(users) == 0:
        raise APIValueError('email', 'Email not exist.')
    user = users[0]  # users 是findall返回的list， users[0],是第一个（惟一一个）元素，是个dict, 里面是一个user类的信息
    # check passwd:
    sha1 = hashlib.sha1()
    sha1.update(user.id.encode('utf-8'))
    sha1.update(b':')
    sha1.update(passwd.encode('utf-8'))   # 这三行等价于先组装再加密 sha1 = hashlib.sha1((user.id+":"+passwd).encode("utf-8"))----即 pw-2,即存到数据库的效果
    if user.passwd != sha1.hexdigest():
        raise APIValueError('passwd', '密码不对啊大兄弟.')
    
    # authenticate ok, set cookie:
    # 用户登录之后,同样的设置一个cookie,与注册用户部分的代码完全一样
    logging.info('handlers模块 ：传入参数与数据库验证通过， 成功登录！')
    r = web.Response()
    r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
    user.passwd = '******'
    r.content_type = 'application/json'
    r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
    return r
#-------------------------------登录------------------------------------------------END



#-------------------------------登出------------------------------------------------START
@get('/signout')
def signout(request):
	# 请求头部的referer，表示从哪里链接到当前页面的，即获得上一个页面，没有则为None
    referer = request.headers.get('Referer')   
    r = web.HTTPFound(referer or '/')   # 如果referer为None，则说明无前一个网址，可能是用户新打开了一个标签页，则转到首页
    # 清理掉cookie的用户信息数据
    r.set_cookie(COOKIE_NAME, '-deleted-', max_age=0, httponly=True)
    logging.info('handlers模块 ：user signed out. 成功登出')
    return r
#-------------------------------登出------------------------------------------------END




# ------------------------------日志管理---------------------------------------------START


# ---------------------------展示全部博文管理页面------------------------------------START
@get('/manage/blogs')       # 如果后面有？page= N , 则会把page 参数一起传去page_index, 然后以 page_index 通过 html 传入 下面的api , 最后返回Page对象
def manage_blogs(request,*, page='1'):
    return {
        '__template__': 'manage_blogs.html',
        'page_index': get_page_index(page),     # get_page_index是开头定义的将页数str转成int的函数
        '__user__':request.__user__
    }

# 在manage_blogs.html中调用，这个是查询
@get('/api/blogs')         
def api_blogs(*, page='1'):    # page由html传入
    page_index = get_page_index(page)  
    num = yield from Blog.findNumber('count(id)')  # num为博客总数
    p = Page(num, page_index)     # 创建Page对象（Page对象在apis.py中定义） 
    if num == 0:
        return dict(page_obj=p, blogs=())   # 若博客数为0, 则手动创建页面对象和空的博客tuple
    # 博客总数不为0,则从数据库中抓取博客
    # limit强制select语句返回指定的记录数,前一个参数为偏移量,后一个参数为该页显示的最大数目，limit由第offset+1开始显示
    blogs = yield from Blog.findAll(orderBy='created_at desc', limit=(p.offset, p.limit))
    return dict(page_obj=p, blogs=blogs)
# ---------------------------展示全部博文管理页面------------------------------------END


# ------------------------------- 展示单页博客---------------------------------------START
# 方法一：根据blog的id查询某页博客的信息，返回的是一个blog对象，单纯用于查询
@get('/api/blog/{id}')
def api_get_blog(*, id):
    blog = yield from Blog.find(id)
    logging.info('fanhuile, %s'%blog.name)
    return blog


# 方法二：显示某一页博客，返回的是一个html
@get('/blog/{id}')
def get_blog(request,*,id):
    blog = yield from Blog.find(id)
    comments = yield from Comment.findAll('blog_id=?', [id], orderBy='created_at desc')
    for c in comments:
        c.html_content = text2html(c.content)             # 将每条评论都转化成html格式
    blog.html_content = markdown2.markdown(blog.content)  # blog是markdown格式,将其转换为html格式
    return {
        '__template__': 'blog.html',
        'blog': blog,
        'comments': comments,
        '__user__':request.__user__
    }

# 把存文本文件转为html格式的文本----用于显示评论
def text2html(text):
    # filter()是‘筛选函数’，接收一个函数和一个序列，filter()把传入的函数依次作用于序列的每个元素，然后根据返回值是True还是false决定保留还是丢弃该元素。这里，是将断行后的数组内容去掉首尾空格，如果还是空，则去掉这个元素
    # 先用filter函数对输入的文本进行过滤处理: 断行,去掉空白字符
    # 再用map函数对特殊符号进行转换,在将字符串装入html的<p>标签中
    lines = map(lambda s: '<p>%s</p>' % s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'), filter(lambda s: s.strip() != '', text.split('\n')))  #strip 是删除头尾的字符，split是根据指定字符分割成字符串数组   
    return ''.join(lines)  # lines是一个字符串列表,将其组装成一个字符串,该字符串即表示html的段落

# ------------------------------- 展示单页博客---------------------------------------END


# --------------------------------写新博文-------------------------------------------START
# 进入创建博客页面
@get('/manage/blogs/create')
def manage_create_blog(request):       
    return {
        '__template__': 'manage_blog_edit.html',
        'id': '',               # id的值将传给js变量ID---------------create 的话传入的id 为空，即新创建
        'action': '/api/createblogs',  # 对应HTML页面中VUE的action名字
        '__user__':request.__user__
    }                           # 将在用户提交博客的时候，将数据post到action制定的路径，此处即为创建博客的api


# 创建博客的api,从js的postJSON函数接收表单信息
@post('/api/createblogs')             
def api_create_blog(request, *, name, summary, content):
    check_admin(request)
    if not name or not name.strip():
        raise APIValueError('name', 'name cannot be empty.')
    if not summary or not summary.strip():
        raise APIValueError('summary', 'summary cannot be empty.')
    if not content or not content.strip():
        raise APIValueError('content', 'content cannot be empty.')
    blog = Blog(user_id=request.__user__.id, user_name=request.__user__.name, user_image=request.__user__.image, name=name.strip(), summary=summary.strip(), content=content.strip())
    yield from blog.save()
    return blog
# ------------------------------- 写新博文-------------------------------------------END


# -------------------------------修改博文--------------------------------------------START
@get('/manage/blogs/edit')
def manage_edit_blog(request,*, id):
    return {
        '__template__': 'manage_blog_edit.html',
        'id': id,
        'action': '/api/updateblogs/%s' % id,
        '__user__':request.__user__
    }

@post('/api/updateblogs/{id}')
def api_update_blog(id, request, *, name, summary, content):
    check_admin(request)
    blog = yield from Blog.find(id)
    if not name or not name.strip():
        raise APIValueError('name', 'name cannot be empty.')
    if not summary or not summary.strip():
        raise APIValueError('summary', 'summary cannot be empty.')
    if not content or not content.strip():
        raise APIValueError('content', 'content cannot be empty.')
    blog.name = name.strip()
    blog.summary = summary.strip()
    blog.content = content.strip()
    yield from blog.update()
    logging.info('成功修改日志 %s' % blog.name)
    return blog
# -------------------------------修改博文--------------------------------------------END


# -------------------------------删除博文--------------------------------------------START
@post('/api/blogs/{id}/delete')
def api_delete_blog(request, *, id):
    check_admin(request)
    blog = yield from Blog.find(id)
    yield from blog.remove()
    logging.info('成功删除日志 %s' % blog.name)
    return dict(id=id)
# -------------------------------删除博文--------------------------------------------END


# ------------------------------日志管理---------------------------------------------END



# -------------------------------评论管理--------------------------------------------START

@get('/manage/')   # 管理页面重定向，以
def manage():
    return 'redirect:/manage/comments'

# 评论管理页面
@get('/manage/comments')
def manage_comments(request, *, page='1'):
    return {
        '__template__': 'manage_comments.html',
        'page_index': get_page_index(page),
        '__user__' : request.__user__
    }

# html通过调用api查看评论
@get('/api/comments')
def api_comments(*, page='1'):
    page_index = get_page_index(page)
    num = yield from Comment.findNumber('count(id)')
    p = Page(num, page_index)
    if num == 0:
        return dict(page_obj=p, comments=())
    comments = yield from Comment.findAll(orderBy='created_at desc', limit=(p.offset, p.limit))
    for c in comments:
        blog=yield from Blog.find(c.blog_id)   # 临时将最新的日志名称赋予评论
        c.blog_name=blog.name
    return dict(page_obj=p, comments=comments)

# html通过调用api删除评论
@post('/api/comments/{id}/delete')
def api_delete_comments(id, request):
    check_admin(request)
    c = yield from Comment.find(id)
    if c is None:
        raise APIResourceNotFoundError('Comment')
    yield from c.remove()
    logging.info('成功删除评论%')
    return dict(id=id)

# 发表评论
@post('/api/blogs/{id}/comments')
def api_create_comment(id, request, *, content):
    user = request.__user__
    if user is None:
        raise APIPermissionError('Please signin first.')
    if not content or not content.strip():
        raise APIValueError('content')
    blog = yield from Blog.find(id)
    if blog is None:
        raise APIResourceNotFoundError('Blog')
    comment = Comment(blog_id=blog.id, user_id=user.id, user_name=user.name, user_image=user.image, content=content.strip())
    yield from comment.save()
    return comment
# -------------------------------评论管理--------------------------------------------END



# -------------------------------用户管理--------------------------------------------START

@get('/manage/users')
def manage_users(request,*, page='1'):
    return {
        '__template__': 'manage_users.html',
        'page_index': get_page_index(page),
        '__user__':request.__user__
    }

# 查询全部用户
@get('/api/users')          # 用户信息接口,用于返回机器能识别的用户信息
def api_get_users(*, page='1'):
    # 获取到要展示的博客页数是第几页
    page_index = get_page_index(page)
    # count为MySQL中的聚集函数，用于计算某列的行数。user_count代表了有多个用户id
    num = yield from User.findNumber('count(id)')
    # 通过Page类来计算当前页的相关信息, 其实是数据库limit语句中的offset，limit
    p = Page(num, page_index)
    if num == 0:
        return dict(page_obj=p, users=())
    # page.offset表示从那一行开始检索，page.limit表示检索多少行
    users = yield from User.findAll(orderBy='created_at desc', limit=(p.offset, p.limit))
    for u in users:
        u.passwd = '******'
    return dict(page_obj=p, users=users)

# 删除用户
@post('/api/users/{id}/delete')
def api_delete_user(id, request):
    check_admin(request)
    u = yield from User.find(id)
    if u is None:
        raise APIResourceNotFoundError('User')
    yield from u.remove()
    logging.info('成功删除用户 %s' % u.name)
    return dict(id=id)