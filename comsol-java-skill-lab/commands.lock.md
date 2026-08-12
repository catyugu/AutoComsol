# commands.lock.md — 本机验证过的命令模板

每条命令附带本机帮助或实际执行证据。所有路径含空格必须引号包裹。

## 版本查询

```bash
comsolcompile -version
# 证据: exit=0, 输出 "COMSOL Multiphysics 6.2.0.290"
# 帮助: comsolcompile -help → exit=0, Usage: comsolcompile [options] files
```

## comsolcompile 帮助语法（本机证据）

```bash
Usage: comsolcompile [options] files

Compile options when compiling a COMSOL Model Java file:
   -classpathadd <classpath>    Additional classpath
   (其余选项为 COMSOL Compiler 应用编译用，本任务不使用)
示例: comsolcompile file.java
```

来源: `comsolcompile -help` 输出，记录于 logs/comsolcompile-help.log

## comsolcompile 编译命令模板

```bash
comsolcompile -classpathadd <额外类路径> <源文件.java>
```

- 输出: 默认在当前目录生成 .class（与源文件同名）；用 `-outputdir <path>` 指定输出目录（此为应用编译选项，Java 模型编译输出跟随源文件目录）
- comsolcompile 由 Eclipse Equinox 启动，自动解析 COMSOL OSGi 类路径（public API 在 com.comsol.api jar）

## comsolbatch 帮助语法（本机证据）

```bash
Usage: <command> [options] [target] [target arguments]
Batch options 关键项:
   -batchlog <log filename>     File to store log in
   -classpathadd <classpath>    Additional classpath
   -inputfile <filename>        The input file name (.mph or .class)
   -outputfile <filename>       The output file name
   -study <study name>          The study to compute
   -job <job name>              The batch job to run
   -methodcall <methodcall tag> The method call to run
   -paramfile / -plist / -pname / -pindex   参数扫描
   -stoptime <seconds>          Max time before stop
   -np <no. of cores>           核心数
   -tmpdir <path>               临时目录
   -recoverydir <path>          恢复目录
   -continue                    继续计算
   -recover                     恢复并继续
   -nosave / -norun             （测试用）
示例: comsolbatch -inputfile <path> -outputfile <path> -study std1
```

来源: `comsolbatch -help` 输出，记录于 logs/comsolbatch-help.log

## comsolbatch 运行 Java 批处理类命令模板

```bash
comsolbatch -inputfile <编译后的Class路径> -outputfile <输出.mph路径> \
  -batchlog <日志路径> -study std1 -np 1 -stoptime 600
```

- inputfile 接受 .mph 或 .class（帮助原文: "The input file name (.mph or .class)"）
- 批处理类要求: public class + `public static void main(String[] args)` 或实现 `com.comsol.model.util.ModelUtil` 标准入口

## 通用调用注意

- 所有路径用引号包裹以支持空格
- comsolbatch 默认前台运行，输出到 stdout 和 -batchlog 指定的文件
- 系统 Java (23) 与 COMSOL 自带 JRE 不同；COMSOL 命令内部使用自带 jre（ini 中 -vm 指向 java/win64/jre）
