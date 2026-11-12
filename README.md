# Garmin 中国区 Codex Skill

这是一个可放入 Codex Cloud 仓库运行的 repo-local Skill。它通过 `garminconnect` 的中国区模式只读获取个人 Garmin Connect 训练与健康数据，默认移除精确位置和常见账户标识，再由 Codex 基于本地证据文件分析训练负荷、睡眠与恢复趋势。

## 本地验证

要求 Python 3.12+：

```bash
python3 -m pip install -r requirements.txt
python3 .agents/skills/garmin-cn-analysis/scripts/garmin_fetch.py --interactive-auth --auth-only
```

首次认证按提示输入 Garmin 用户名、密码，在 Garmin 要求验证时输入收到的手机短信验证码。密码和验证码输入不回显。成功后 token 默认保存到 `.garmin-tokens/garmin_tokens.json`，可通过 `GARMIN_TOKEN_STORE` 指定其他存储目录。`--auth-only` 只完成认证，不获取训练或健康数据。

后续直接复用 token 获取数据：

```bash
python3 .agents/skills/garmin-cn-analysis/scripts/garmin_fetch.py --days 28
```

也可使用环境变量 `GARMIN_USERNAME`、`GARMIN_PASSWORD` 和单次有效的 `GARMIN_MFA_CODE`；旧的 `GARMIN_EMAIL` 仍兼容。交互模式会优先复用有效 token，仅在需要重新登录时询问用户名、密码和验证码。

数据输出位于 `artifacts/garmin/`，该目录已加入 `.gitignore`。推荐首次在可信本机完成认证，把生成的 `garmin_tokens.json` 作为 Codex Cloud 的 `GARMIN_TOKENS_JSON` Secret；不要提交 token 文件。详细配置见 [Cloud setup](.agents/skills/garmin-cn-analysis/references/cloud-setup.md)。

在 Codex 中使用：

```text
Use $garmin-cn-analysis to analyze my last 28 days of Garmin China training and recovery data.
```

## 接口边界

此项目面向个人账号，使用非官方 Garmin Connect Web 接口，可能随 Garmin 服务变更而失效。Garmin 官方 Health API 需要企业项目申请与审批；多用户或商业场景应改接官方 API。
