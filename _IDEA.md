# 一些想法


## yaml dsl

call_by, loader 等需要用路径:函数的语法 import路径支持相对路径



## 项目qa

这个链路

docker run --rm -v "/home/l8ng/Projects/__straydragon__/scalim:/repo" -w /repo python:3.6 python -m compileall -q src/scalim
docker run --rm -v "/home/l8ng/Projects/__straydragon__/scalim:/repo" -w /repo python:3.6 bash /repo/scripts/check-py36-typingext-docker.sh

需要调整为 有 CI 环境变量直接用 pypi 没有用国内镜像