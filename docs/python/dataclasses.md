`dataclasses` 是 Python 3.7+ 引入的**标准库**，用于**快速创建主要用于存储数据的类**（常称为“数据类”）。它能自动生成 `__init__`、`__repr__`、`__eq__` 等样板方法，大幅减少冗余代码，让代码更简洁、更易读。


### 一、为什么要用 `dataclasses`？
在没有 `dataclasses` 之前，定义一个存储数据的类需要写很多重复代码：

#### 普通类写法（样板代码多）
```python
class Person:
    def __init__(self, name: str, age: int, city: str = "Unknown"):
        self.name = name
        self.age = age
        self.city = city

    def __repr__(self):
        # 用于打印对象时的友好显示
        return f"Person(name='{self.name}', age={self.age}, city='{self.city}')"

    def __eq__(self, other):
        # 用于比较两个对象是否相等
        if not isinstance(other, Person):
            return False
        return (self.name, self.age, self.city) == (other.name, other.age, other.city)

# 使用
p1 = Person("Alice", 30)
p2 = Person("Alice", 30)
print(p1)       # Person(name='Alice', age=30, city='Unknown')
print(p1 == p2) # True
```

#### 用 `dataclasses` 改写（代码量减少 70%）
```python
from dataclasses import dataclass

@dataclass
class Person:
    name: str
    age: int
    city: str = "Unknown"

# 使用方式完全一样，但自动拥有了 __init__、__repr__、__eq__
p1 = Person("Alice", 30)
p2 = Person("Alice", 30)
print(p1)       # Person(name='Alice', age=30, city='Unknown')
print(p1 == p2) # True
```

**核心优势**：`@dataclass` 装饰器自动帮你生成了 `__init__`、`__repr__`、`__eq__` 等方法，你只需要专注于定义字段和类型提示。


### 二、核心用法：`@dataclass` 装饰器
`@dataclass` 是最核心的装饰器，放在类定义上方即可将其标记为数据类。

#### 1. 基本字段定义
数据类的字段通过**类型提示**定义，语法为 `字段名: 类型`：
```python
from dataclasses import dataclass

@dataclass
class Point:
    x: float  # 必填字段（无默认值）
    y: float  # 必填字段
    z: float = 0.0  # 可选字段（有默认值）
```

#### 2. 自动生成的方法
`@dataclass` 默认会生成以下方法：
| 方法          | 作用                                                                 |
|---------------|----------------------------------------------------------------------|
| `__init__`    | 初始化方法，按字段顺序接收参数并赋值给 `self`。                     |
| `__repr__`    | 字符串表示方法，打印对象时显示 `类名(字段1=值1, 字段2=值2, ...)`。 |
| `__eq__`      | 相等比较方法，按字段顺序比较两个对象的所有字段是否相等。             |


### 三、高级字段控制：`field()` 函数
对于需要更精细控制的字段（如排除在 `__repr__` 外、设置可变默认值等），可以使用 `dataclasses.field()` 函数。

#### 1. 常用 `field()` 参数
| 参数          | 类型      | 默认值 | 作用                                                                 |
|---------------|-----------|--------|----------------------------------------------------------------------|
| `default`     | Any       | -      | 字段的默认值（与直接在字段后写 `= 默认值` 效果一致）。             |
| `default_factory` | callable | -      | 用于生成默认值的函数（**必须用于可变对象的默认值**，如 `list`/`dict`）。 |
| `init`        | bool      | `True` | 是否将字段包含在 `__init__` 的参数中（`False` 表示不能通过构造函数赋值）。 |
| `repr`        | bool      | `True` | 是否将字段包含在 `__repr__` 的输出中。                               |
| `compare`     | bool      | `True` | 是否将字段包含在 `__eq__` 和比较方法中。                             |
| `hash`        | bool | `None` | 是否将字段包含在 `__hash__` 计算中（`None` 表示根据 `compare` 和 `frozen` 自动决定）。 |

#### 2. 关键场景：可变对象的默认值（必须用 `default_factory`）
**错误写法**（会导致所有实例共享同一个列表）：
```python
@dataclass
class Student:
    name: str
    hobbies: list = []  # ❌ 危险！所有实例会共享这个列表
```

**正确写法**（用 `default_factory` 为每个实例生成新列表）：
```python
from dataclasses import dataclass, field

@dataclass
class Student:
    name: str
    hobbies: list = field(default_factory=list)  # ✅ 每个实例有独立的空列表

# 验证
s1 = Student("Alice")
s2 = Student("Bob")
s1.hobbies.append("reading")
print(s1.hobbies)  # ['reading']
print(s2.hobbies)  # []（互不影响）
```

#### 3. 排除字段：`init=False` 或 `repr=False`
```python
@dataclass
class User:
    username: str
    password: str = field(repr=False)  # 密码不显示在 __repr__ 中
    created_at: str = field(init=False, default="2024-01-01")  # 不能通过构造函数赋值

u = User("alice", "123456")
print(u)  # User(username='alice', created_at='2024-01-01')（密码被隐藏）
```


### 四、`@dataclass` 装饰器的常用参数
`@dataclass` 本身也接受参数，用于控制生成方法的行为：

| 参数          | 类型      | 默认值 | 作用                                                                 |
|---------------|-----------|--------|----------------------------------------------------------------------|
| `frozen`      | bool      | `False` | 若为 `True`，则类实例**不可变**（创建后不能修改字段值）。           |
| `order`       | bool      | `False` | 若为 `True`，则自动生成 `__lt__`、`__le__`、`__gt__`、`__ge__` 方法（按字段顺序比较大小）。 |
| `kw_only`     | bool      | `False` | 若为 `True`，则所有字段必须通过**关键字参数**传递（不能用位置参数）。 |
| `repr`        | bool      | `True` | 是否生成 `__repr__` 方法。                                           |
| `eq`          | bool      | `True` | 是否生成 `__eq__` 方法。                                             |

#### 1. 不可变数据类：`frozen=True`
```python
@dataclass(frozen=True)
class Point:
    x: float
    y: float

p = Point(1.0, 2.0)
# p.x = 3.0  # ❌ 报错：FrozenInstanceError: cannot assign to field 'x'
```

#### 2. 自动生成比较方法：`order=True`
```python
@dataclass(order=True)
class Score:
    value: int
    name: str

s1 = Score(85, "Alice")
s2 = Score(90, "Bob")
print(s1 < s2)  # True（先比较 value，再比较 name）
```

#### 3. 强制关键字参数：`kw_only=True`
```python
@dataclass(kw_only=True)
class Config:
    host: str
    port: int
    timeout: int = 30

# c = Config("localhost", 8080)  # ❌ 报错：必须用关键字参数
c = Config(host="localhost", port=8080)  # ✅ 正确
```


### 五、其他实用功能
#### 1. `__post_init__`：初始化后执行额外逻辑
如果需要在 `__init__` 执行完后做一些额外的初始化或验证，可以定义 `__post_init__` 方法：
```python
@dataclass
class Person:
    name: str
    age: int

    def __post_init__(self):
        # 验证年龄必须大于 0
        if self.age <= 0:
            raise ValueError("Age must be positive")

# Person("Alice", 0)  # ❌ 报错：ValueError: Age must be positive
```

#### 2. 辅助函数：`asdict()`、`astuple()`、`replace()`
```python
from dataclasses import dataclass, asdict, astuple, replace

@dataclass
class Point:
    x: float
    y: float

p = Point(1.0, 2.0)

# 1. 转换为字典
print(asdict(p))  # {'x': 1.0, 'y': 2.0}

# 2. 转换为元组
print(astuple(p))  # (1.0, 2.0)

# 3. 创建修改后的新实例（不修改原实例）
p2 = replace(p, x=3.0)
print(p)   # Point(x=1.0, y=2.0)
print(p2)  # Point(x=3.0, y=2.0)
```


### 六、继承：数据类的子类化
数据类支持继承，子类会自动继承父类的字段和方法：
```python
@dataclass
class Animal:
    name: str
    age: int

@dataclass
class Dog(Animal):
    breed: str  # 子类新增字段
    sound: str = "Woof"

d = Dog(name="Buddy", age=3, breed="Golden Retriever")
print(d)  # Dog(name='Buddy', age=3, breed='Golden Retriever', sound='Woof')
```

**注意**：如果父类有带默认值的字段，子类新增的字段也必须有默认值（否则会报错“非默认参数不能跟在默认参数后面”）。


### 总结
`dataclasses` 是 Python 中处理数据类的神器，核心价值在于：
1. **减少样板代码**：自动生成 `__init__`、`__repr__`、`__eq__` 等方法。
2. **提高可读性**：专注于字段定义，代码意图更清晰。
3. **灵活控制**：通过 `field()` 和装饰器参数满足各种复杂需求。

对于主要用于存储数据的类（如配置项、API 响应模型、数据库实体等），优先考虑使用 `dataclasses`。