SoilSense backend CORS fix

1. Replace the files in your backend repository with these files (do not upload soilsense.db).
2. Confirm requirements.txt includes Flask-Cors.
3. In Render > Soil-Sense > Environment, set:
   FRONTEND_URL=https://soilsense-frontend-pe0n.onrender.com
4. Commit and push the backend files to the GitHub repository connected to Render.
5. Wait for the backend deployment to finish.
6. Open the frontend and hard refresh with Ctrl+Shift+R.
7. In DevTools, check that GET https://soil-sense.onrender.com/api/sensor now has
   Access-Control-Allow-Origin: https://soilsense-frontend-pe0n.onrender.com

The code allows both the current frontend URL and the previous frontend URL, while
keeping FRONTEND_URL configurable. The database file is intentionally not included.
