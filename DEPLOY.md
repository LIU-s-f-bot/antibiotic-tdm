# 部署到 Streamlit Community Cloud（免费、固定公网链接）

部署后获得固定地址 `https://<你的应用名>.streamlit.app`，**Mac 关机也照常运行**。

## 前置条件
- GitHub 账号（没有就到 https://github.com 免费注册）
- Streamlit Cloud 账号（用 GitHub 账号直接登录即可）
- ⚠️ 代码会放在**公开** GitHub 仓库（免费版要求）。本应用只有剂量公式，无患者数据。

---

## 第 1 步：把代码放到 GitHub（公开仓库）

### 方式 A：网页上传（零安装，推荐首次）
1. 登录 https://github.com → 右上角 **+** → **New repository**
2. Repository name 填 `antibiotic-tdm`；选 **Public**；**不要**勾选 Add README / .gitignore；点 **Create repository**
3. 进入空仓库 → 点 **uploading an existing file**（或 **Add file → Upload files**）
4. 把本目录下这 6 个文件**拖进去**：`.gitignore`、`README.md`、`DEPLOY.md`、`app.py`、`drug_configs.py`、`logic.py`、`requirements.txt`
   - （隐藏文件 `.gitignore` 在 macOS 访达里按 `Cmd+Shift+.` 可见）
5. 点 **Commit changes**

### 方式 B：gh CLI（方便以后更新代码）
```bash
brew install gh
gh auth login            # 浏览器登录 GitHub
cd "/Users/liushuangfei/Research/医科院抗生素"
gh repo create antibiotic-tdm --public --source=. --push
```

---

## 第 2 步：在 Streamlit Cloud 部署
1. 打开 https://share.streamlit.io
2. 用 GitHub 账号登录
3. 点 **New app**（或 Create app）
4. 填：
   - **Repository**：选你的 `antibiotic-tdm` 仓库
   - **Branch**：`main`
   - **Main file path**：`app.py`
   - （Requirements 会自动读 `requirements.txt`）
5. 点 **Deploy!** —— 首次构建约 1–3 分钟
6. 完成后顶部出现固定链接：`https://antibiotic-tdm.streamlit.app`（具体名字视可用性）

---

## 注意事项
- **休眠**：免费版应用 **7 天无人访问会自动休眠**；下次打开冷启动约 30s–1min 后唤醒。常打开就不会休眠。
- **国内访问**：`streamlit.app` 服务器在境外，国内访问**可能偏慢或偶尔打不开**——部署后请先用手机实测。若不可用，可改回 cloudflared 隧道方案。
- **更新代码**：改完代码 push 到 GitHub（或网页上传覆盖）→ Streamlit Cloud 会自动检测并重新部署（也可手动点 Retry / Reboot）。

## 本地预览
```bash
cd "/Users/liushuangfei/Research/医科院抗生素"
python3 -m streamlit run app.py
```
