# SoilSense Login - Ready

1. Put these files inside your existing `backend` folder.
2. Run `INSTALL_AUTH.bat` once. It automatically connects login to `app.py` and adds Authlib.
3. On Render, add: `SECRET_KEY`, `FRONTEND_URL=https://soil-sense-frontend.onrender.com`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`.
4. Google OAuth redirect URI:
`https://soil-sense.onrender.com/api/auth/google/callback`
5. Deploy backend, then upload `index.html`, `script.js`, and `style.css` to the frontend repo.

Google client secret stays only on the backend/Render.
