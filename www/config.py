#!/usr/bin/env python3
#-*-coding:utf-8-*-

'configuration'

print('this import file__name__==',__name__)

__author__='chch'

import os
import sys
from imp import reload
# sys.path.append(r'c:/users/志冲/desktop/pytest')

#-----------start-----------

import config_default

class Dict(dict):

	def __init__(self,names=(),values=(),**kw):
		super(Dict,self).__init__(**kw)
		for k,v in zip(names,values):  #zip函数就是将两个序列对应位置变成一个tuple作为list的对应位置一个元素
			self[k]=v

	def __getattr__(self,key):
		try:
			return self[key]
		except KeyError:
			raise AttributeError(r"'Dict' object has no attribute '%s'" %key)

	def __setattr__(self,key,value):
		self[key]=value


# 将默认配置文件与自定义配置文件进行混合
def merge(defaults,override):
	r={}
	for k, v in defaults.items():      	
		if k in override:			 #1. 检查默认配置里面的参数是不是在override里面也有
			if isinstance(v,dict):   #2-1. 如果有，而且又是个dict,则递归调用本函数, 递归到2-2为止
				r[k] = merge(v,override[k]) 
			else:					 #2-2，如果有，但不是个dict,则取override的值放到r
				r[k] = override[k]
		else:						 #3.   如果override里面没有，则取默认的放到r
			r[k] = v
	return r


# 将内建字典转换成自定义字典类型
def toDict(d):
	D = Dict()
	for k,v in d.items():
		# 字典某项value仍是字典的(比如"db"),则将value的字典也转换成自定义字典类型
		D[k] = toDict(v) if isinstance(v,dict) else v
	return D


# 取得默认配置文件的配置信息
configs = config_default.configs

try:
	import config_override
	configs = merge(configs,config_override.configs)
except ImportError:    #导入自定义配置失败就直接pass
	pass


# 最后将混合好的配置字典变成自定义字典类型,方便取值与设值
configs = toDict(configs)