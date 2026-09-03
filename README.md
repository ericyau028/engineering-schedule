# 工程排程表

工程工作時間表網頁，與賽事版使用相同架構，但欄位改為工程用途：

- 內容
- 負責人
- 項目分鐘

## 啟動

方法一：雙擊 `start.bat`

方法二：在 terminal 執行

```bat
cd /d D:\AI\Codex-Secretary\engineering-app
python server.py
```

瀏覽器打開 http://127.0.0.1:8780

## 功能

- 時間表依照日期分組，過去、30 分鐘內、進行中會顯示不同顏色
- 每組資料自動產生「開始」與「結束」兩列，並以關聯線連接
- 跨午夜會自動歸到下一日
- 新增表單輸入日期、開始時間、內容、負責人、項目分鐘、描述、結束時間
- 編輯時可自由修改欄位與關聯
- 批量刪除：可刪除指定日期或之前的所有時間段，或清空全部
- 資料儲存在 `data/schedule.json`

## GitHub Pages 網頁版

網頁版使用瀏覽器 localStorage 儲存資料：

- 首次打開會讀取 `public/schedule-static.json` 的初始時間表
- 更新初始資料後執行 `python export_static.py` 再 push
- GitHub Actions 會自動部署 `public/`
