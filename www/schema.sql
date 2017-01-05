-- schema.sql
/* sql初始化脚本2017-01-03
多行注释用这个
单行注释用两横
注意两横之后要有空格不然会报错 */

drop database if exists awesome;
create database awesome;

use awesome;

-- 用于建一个新用户www-data，密码也是www-data，授权4个功能，仅能在本地登录
grant select,insert,update,delete on awesome.* to 'www-data'@'localhost' identified by 'www-data';

create table users (
	`id` varchar(50) not null,
	`email` varchar(50) not null,
	`passwd` varchar(50) not null,
	`admin` bool not null,
	`name` varchar(50) not null,
	`image` varchar(500) not null,
	`created_at` real not null,
	unique key `idx_email`(`email`), -- UNIQUE KEY主要是用来防止数据插入的时候重复，即通过email来建立叫做idx_email的唯一索引，可以为NULL
	key `idx_created_at` (`created_at`),-- 为create_at创建叫做idx_create_at的索引，增加查询速度
	primary key(`id`) -- 主键是不能为NULL的
)engine=innodb default charset = utf8; -- 使用innodb作为存储引擎，还有例如MyIASM等其他引擎

create table blogs (
	`id` varchar(50) not null,
	`user_id` varchar(50) not null,
	`user_name` varchar(50) not null,
	`user_image` varchar(500) not null,
	`name` varchar(50) not null,
	`summary` varchar(200) not null,
	`content` mediumtext not null,
	`created_at` real not null,
	key `idx_created_at` (`created_at`),
	primary key(`id`)
) engine=innodb default charset=utf8;

create table comments (
	`id` varchar(50) not null,
	`blog_id` varchar(50) not null,
	`user_id` varchar(50) not null,
	`user_name` varchar(50) not null,
	`user_image` varchar(500) not null,
	`content` mediumtext not null,
	`created_at` real not null,
	key `idx_created_at` (`created_at`),
	primary key(`id`)
)engine=innodb default charset=utf8;



	