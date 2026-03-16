# 数据库表结构设计

## 1. gather_select_dic_data (字典数据表)
| 字段名 | 类型 | 说明 |
|--------|------|------|
| dicdstalid | PK | 字典数据ID |
| dicid | FK | 字典ID |
| dicddataname | | 字典数据名称 |

## 2. gather_tree_dic_query (树形字典查询表)
| 字段名 | 类型 | 说明 |
|--------|------|------|
| ID | PK | 主键ID |
| NAME | | 名称 |
| PID | | 父级ID |

## 3. gather_tree_dic_zpjg (树形字典-组织机构表)
| 字段名 | 类型 | 说明 |
|--------|------|------|
| ID | PK | 主键ID |
| NAME | | 名称 |
| PID | | 父级ID |

## 4. gather_select_dic (字典选择表)
| 字段名 | 类型 | 说明 |
|--------|------|------|
| dicid | PK | 字典ID |
| dicname | | 字典名称 |
| dicms | | 字典描述 |
| diclength | | 字典长度 |

## 5. gather_task_user (任务用户关联表)
| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | PK | 主键ID |
| userid | | ��户ID |
| taskid | FK | 任务ID |
| time | | 时间 |


## 6. gather_task (采集任务表)
| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | PK | 任务ID |
| name | | 任务名称 |
| table_name | | 表名 |
| status | | 状态 |
| create_time | | 创建时间 |
| update_time | | 更新时间 |

## 7. gather_field (字段配置表)
| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | PK | 字段ID |
| taskid | FK | 任务ID |
| field_name | | 字段名称 |
| field_type | | 字段类型 |
| field_length | | 字段长度 |
| is_required | | 是否必填 |

## 表关系说明

- `gather_task` 与 `gather_task_user` 为一对多关系
- `gather_task` 与 `gather_field` 为一对多关系
- `gather_select_dic` 与 `gather_select_dic_data` 为一对多关系
