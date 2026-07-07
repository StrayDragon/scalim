#!/bin/bash

# 将当前脚本中所有已归档的变更使用7z添加到 freezed_changes.7z.archived 中 避免ai误读和更改

SCRIPT_DIR_PATH=$(dirname $(realpath $0))

cd $SCRIPT_DIR_PATH

# 获取所有已归档的变更
archived_changes=$(ls -d 2026-*)

# 将所有已归档的变更使用7z添加到 freezed_changes.7z.archived 中
for change in $archived_changes; do
   7z a freezed_changes.7z.archived $change
   # 删除原目录
   rm -rf $change
done


