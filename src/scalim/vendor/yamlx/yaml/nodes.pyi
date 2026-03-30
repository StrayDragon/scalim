from typing import List, Tuple


class Node:
    ...


class ScalarNode(Node):
    ...


class SequenceNode(Node):
    value: List[Node]


class MappingNode(Node):
    value: List[Tuple[Node, Node]]
