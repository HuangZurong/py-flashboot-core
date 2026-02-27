# FlashBoot Core — Roadmap

> A lightning-fast, Spring Boot-inspired framework for Python.

FlashBoot Core 定位为 Python 开发的通用基础库，补齐标准库未覆盖的常用基础能力，为上层应用（Web、CLI、数据处理、微服务等）提供统一的底层支撑。

---

## 当前已有能力（v0.1.x）

| 模块 | 状态 | 说明 |
|------|------|------|
| `env` — 配置管理 | ✅ 已完成 | Profile 检测、YAML 加载、深度合并、占位符解析、`@property_bind` |
| `event_bus` — 同步事件总线 | ✅ 已完成 | 发布/订阅、优先级排序、装饰器订阅 |
| `event_bus` — 异步事件总线 | 🔲 Stub | 待实现 |
| `io` — 资源抽象 | ✅ 已完成 | Resource 接口、FileSystemResource |
| `utils` — 项目工具 | ✅ 已完成 | 项目根路径智能发现 |
| `exceptions` — 异常体系 | ✅ 基础 | FlashBootException 基类 |

---

## Phase 1 — 核心容器

**目标：** 引入 IoC/DI，将独立模块串联为真正的"框架"。

- [ ] 轻量 IoC 容器
  - Bean 注册与获取
  - 作用域管理（singleton / prototype）
- [ ] 依赖注入
  - `@Component` 标记组件
  - `@Inject` 构造器/属性注入
  - 循环依赖检测
- [ ] 组件扫描
  - 自动发现指定包下的 `@Component`
  - 手动注册 API
- [ ] 生命周期管理
  - `@PostConstruct` / `@PreDestroy`
  - 容器启动/关闭事件
- [ ] 完成 `AsyncEventBus` 实现

---

## Phase 2 — 配置增强

**目标：** 让配置系统更强大、更灵活，覆盖 Python 开发中常见的配置场景。

- [ ] `@PropertyBind` 与 DI 容器打通
  - 配置类作为 Bean 自动注入
- [ ] 多配置源支持
  - `.properties` / `.toml` 格式加载器
  - 环境变量配置源
  - 命令行参数配置源
  - 配置源优先级链（CLI > 环境变量 > profile 文件 > 默认文件）
- [ ] 配置校验
  - 结合 Pydantic validation
  - 启动时校验必填项与类型
- [ ] 配置热加载
  - 文件变更检测
  - 变更事件通知（与 event_bus 联动）

---

## Phase 3 — 弹性与并发

**目标：** 提供 Python 开发中高频需要但标准库缺失的弹性和并发工具。

- [ ] 重试机制
  - `@Retry(max_attempts, backoff, on_exception)`
  - 指数退避、固定间隔等策略
- [ ] 熔断器
  - `@CircuitBreaker(threshold, timeout)`
  - 半开/全开/关闭状态管理
- [ ] 限流
  - `@RateLimiter(calls, period)`
  - 令牌桶 / 滑动窗口
- [ ] 超时控制
  - `@Timeout(seconds)`
  - 同步/异步统一接口
- [ ] 并发工具
  - 线程池 / 协程池封装
  - `@Async` 异步执行装饰器
  - 并发任务编排（类似 `asyncio.gather` 的高层封装）

---

## Phase 4 — 数据与缓存

**目标：** 提供数据访问和缓存的通用抽象。

- [ ] 连接池管理
  - 统一连接池接口
  - 连接健康检查与自动回收
- [ ] Repository 模式
  - 通用 CRUD 抽象
  - 查询构建器
- [ ] 事务管理
  - `@Transactional`
  - 事务传播机制
- [ ] 缓存抽象
  - `@Cacheable` / `@CacheEvict` / `@CachePut`
  - 内置内存缓存（TTL、LRU）
  - 可插拔后端（Redis 等）

---

## Phase 5 — 开发者体验

**目标：** 提升日常开发效率，让框架更好用。

- [ ] AOP 支持
  - `@Before` / `@After` / `@Around`
  - 基于装饰器的轻量实现
- [ ] 定时任务
  - `@Scheduled(cron="...")` / `@Scheduled(interval=...)`
  - 任务管理与取消
- [ ] 条件装配
  - `@ConditionalOnProperty` / `@ConditionalOnClass`
- [ ] 插件/扩展点机制
  - SPI（Service Provider Interface）
  - 上层库接入协议
- [ ] 序列化增强
  - 统一序列化接口（JSON / YAML / TOML / Pickle）
  - 自定义序列化器注册
- [ ] 测试辅助
  - 测试上下文支持
  - Mock Bean 注入
  - 配置覆盖

---

## Phase 6 — 成熟度

**目标：** 生产就绪，社区友好。

- [ ] 结构化日志
  - 基于 loguru 的统一日志配置
  - 日志格式与级别通过配置文件管理
  - 上下文追踪（trace_id）
- [ ] 完善异常体系
  - 模块级异常分类
  - 异常链与上下文信息
- [ ] 文档与示例
  - API 文档
  - Quick Start 示例项目
  - 最佳实践指南
- [ ] 发布
  - PyPI 发布流程
  - 版本管理规范（SemVer）
  - CHANGELOG 维护

---

## 设计原则

1. **轻量优先** — 最小依赖，按需引入，不强制绑定
2. **约定优于配置** — 合理的默认值，零配置可用
3. **可扩展** — 核心小而稳，通过插件机制扩展
4. **Pythonic** — 充分利用装饰器、类型提示、上下文管理器等 Python 特性，而非照搬 Java 模式
5. **标准库补位** — 只做标准库没做好或没覆盖的事，不重复造轮子
