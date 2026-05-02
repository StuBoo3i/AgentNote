Typer 是一个由 **FastAPI 作者（Sebastián Ramírez）** 开发的现代 Python 命令行界面（CLI）框架，它基于 **Click**（一个成熟的 CLI 库）和 **Python 类型提示（Type Hints）** 构建，以“**简单、强大、自动生成文档**”为核心特点。


### 一、Typer 的核心优势
1. **基于类型提示**：利用 Python 原生的 `int`/`str`/`Path` 等类型注解，自动完成**参数类型转换**和**验证**，无需额外代码。
2. **自动生成帮助文档**：根据函数签名、文档字符串和类型提示，自动生成美观的 `--help` 信息。
3. **极简语法**：用最少的代码实现复杂的 CLI 逻辑，学习曲线平缓。
4. **兼容 Click**：底层基于 Click，可直接复用 Click 的生态和高级功能。
5. **IDE 友好**：类型提示让 IDE（如 PyCharm、VS Code）能提供精准的智能补全。


### 二、核心概念与基础用法
#### 1. 安装
```bash
pip install typer
# 可选：安装 rich 以获得更美观的终端输出
pip install rich
```


#### 2. 最小示例：Hello World
```python
import typer

# 1. 创建 Typer 应用实例
app = typer.Typer()

# 2. 定义命令（用 @app.command() 装饰函数）
@app.command()
def hello(name: str):
    """简单的问候命令"""
    typer.echo(f"Hello {name}!")

# 3. 运行应用
if __name__ == "__main__":
    app()
```

运行效果：
```bash
# 执行命令
python script.py hello Alice
# 输出：Hello Alice!

# 查看帮助
python script.py --help
# 自动生成的帮助文档会显示命令列表和参数说明
```


#### 3. 核心组件详解
| 组件          | 作用                                                                 |
|---------------|----------------------------------------------------------------------|
| `Typer()`     | 创建 CLI 应用的核心实例，所有命令和回调都绑定到它。                 |
| `@app.command()` | 装饰器，将普通函数转换为 **CLI 子命令**。                           |
| `@app.callback()` | 装饰器，定义 **顶层回调函数**（用于全局帮助信息或前置逻辑）。       |
| 函数参数       | 通过类型提示自动定义为 **位置参数**（Arguments）或 **选项参数**（Options）。 |
| `typer.echo()` | 安全的终端输出函数（兼容 Python 2/3，处理编码问题）。              |


### 三、参数与选项：类型提示的魔法
Typer 通过**函数参数的类型提示**自动区分“位置参数”和“选项参数”，并完成类型转换。

#### 1. 位置参数（Arguments）
- 没有默认值的参数会被自动定义为**位置参数**（必须按顺序传入）。
- 示例：
  ```python
  @app.command()
  def add(a: int, b: int):
      """计算两个数的和"""
      typer.echo(f"Result: {a + b}")
  ```
  运行：`python script.py add 1 2` → 输出 `Result: 3`


#### 2. 选项参数（Options）
- 有默认值的参数会被自动定义为**选项参数**（以 `--` 开头，顺序不限）。
- 示例：
  ```python
  @app.command()
  def greet(name: str, formal: bool = False):
      """问候命令，支持正式/非正式模式"""
      if formal:
          typer.echo(f"Good day, {name}.")
      else:
          typer.echo(f"Hey {name}!")
  ```
  运行：
  - `python script.py greet Alice` → `Hey Alice!`
  - `python script.py greet Alice --formal` → `Good day, Alice.`


#### 3. 高级参数控制：`typer.Option()` 和 `typer.Argument()`
若需更精细的控制（如设置帮助文本、限制取值范围），可使用 `typer.Option()` 或 `typer.Argument()`：
```python
@app.command()
def download(
    url: str = typer.Argument(..., help="要下载的文件 URL"),  # ... 表示必填
    output: Path = typer.Option(Path("output.txt"), help="保存路径"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="静默模式"),
):
    """下载文件的命令"""
    if not quiet:
        typer.echo(f"Downloading from {url} to {output}...")
    # 下载逻辑...
```


### 四、子命令与命令组
Typer 支持**多级子命令**，适合构建复杂的 CLI 工具（如 `git` 那样的层级结构）。

#### 示例：多命令组
```python
import typer

app = typer.Typer()

# 1. 创建子命令组
db_app = typer.Typer()
app.add_typer(db_app, name="db")  # 将子组绑定到主应用

# 2. 为子组添加命令
@db_app.command("init")
def db_init():
    """初始化数据库"""
    typer.echo("Database initialized.")

@db_app.command("migrate")
def db_migrate():
    """执行数据库迁移"""
    typer.echo("Database migrated.")

# 3. 主应用的其他命令
@app.command()
def serve():
    """启动服务器"""
    typer.echo("Server started.")

if __name__ == "__main__":
    app()
```

运行效果：
```bash
python script.py db init    # 调用子命令：Database initialized.
python script.py serve       # 调用主命令：Server started.
```


### 五、高级特性
1. **参数验证**：利用类型提示或 `typer.Option()` 的 `callback` 参数自定义验证逻辑。
2. **环境变量支持**：通过 `envvar` 参数让选项从环境变量读取值。
3. **上下文（Context）**：共享状态或访问 Click 底层对象。
4. **自动补全**：支持 Shell 自动补全（需额外配置）。


### 六、总结
Typer 是一个**“开箱即用”**的 CLI 框架，它通过 Python 类型提示将“参数解析、类型转换、文档生成”等繁琐工作自动化，让你能专注于业务逻辑。如果你熟悉 FastAPI，Typer 的设计理念会让你倍感亲切；即使是新手，也能快速写出专业的 CLI 工具。