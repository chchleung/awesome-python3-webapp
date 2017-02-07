#!/usr/bin/env python3
#-*-coding:utf-8-*-

'api errors module'

print('this import file__name__==',__name__)

__author__='chch'

import os
import sys
from imp import reload

#----------start----------------
# 几个简单的api错误异常类，用于抛出异常
'''
JSON API definition.
'''

import json, logging, inspect, functools

class APIError(Exception):
    '''
    the base APIError which contains error(required), data(optional) and message(optional).
    '''
    def __init__(self, error, data='', message=''):
        super(APIError, self).__init__(message)
        self.error = error
        self.data = data
        self.message = message


class APIValueError(APIError):
    '''
    Indicate the input value has error or invalid. The data specifies the error field of input form.
    表明输入的值错误或不合法.
    data属性指定为输入表单的错误域
    '''
    def __init__(self, field, message=''):
        super(APIValueError, self).__init__('value:invalid', field, message)


class APIResourceNotFoundError(APIError):
    '''
    Indicate the resource was not found. The data specifies the resource name.
    表明找不到指定资源.
    data属性指定为资源名
	'''
    def __init__(self, field, message=''):
        super(APIResourceNotFoundError, self).__init__('value:notfound', field, message)


class APIPermissionError(APIError):
    '''
    Indicate the api has no permission.
    表明没有权限
    '''
    def __init__(self, message=''):
        super(APIPermissionError, self).__init__('permission:forbidden', 'permission', message)



# ----------------------------------------------编写Page 分页对象------------------------START
class Page(object):   # page对象,用于储存分页信息
    '''
    Page object for display pages.
    '''

    def __init__(self, item_count, page_index=1, page_size=10):   # 博客总数，显示页码，一个页面最多显示的博文数目
        self.item_count = item_count   # 从数据库中查询博客的总数获得
        self.page_size = page_size     # 可自定义,或使用默认值
        # 页面数目,由博客总数与每页的博客数共同决定
        # item_count 不能被page_size整除时,最后一页的博客数目不满page_size,但仍需独立设立一页
        # 以下式子等价与 math.ceil(item_count / page_size)，返回大于参数x的最小整数,即对浮点数向上取整
        self.page_count = item_count // page_size + (1 if item_count % page_size > 0 else 0)
        
        # offset为偏移量,limit为限制数目,将被用于获取博客的api
        # 比如共有98篇博客,page_size=10, 则page_count=10.
        # 当前page_index=9,即这一页的博客序号(假设有)为81-90.此时offset=80
        if (item_count == 0) or (page_index > self.page_count):
            # 没有博客,或页码出错,将offset,limit置为0,页码置为1
            self.offset = 0
            self.limit = 0
            self.page_index = 1
        else:   # 有博客,且指定页码并未超出页面总数的
            self.page_index = page_index     # 页码置为指定的页码
            self.offset = self.page_size * (page_index - 1)    # 设置页面偏移量
            self.limit = self.page_size      # 页面的博客限制数与页面大小一致
        self.has_next = self.page_index < self.page_count   # 页码小于页面总数,说有有下页
        self.has_previous = self.page_index > 1          # > 若页码大于1,说明有前页

    def __str__(self):  # 返回页面信息
        return 'item_count: %s, page_count: %s, page_index: %s, page_size: %s, offset: %s, limit: %s' % (self.item_count, self.page_count, self.page_index, self.page_size, self.offset, self.limit)

    __repr__ = __str__   # str是显示给用户用的，repr是给机器用的