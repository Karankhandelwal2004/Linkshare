# Deploying LinkShare to Render

This guide walks you through deploying the LinkShare FastAPI app to Render.

## Prerequisites

- GitHub account (repo already there: https://github.com/Karankhandelwal2004/Linkshare.git)
- MongoDB Atlas cluster running (you already have this connected)
- Render account (free tier available): https://render.com

## Step 1: Get your MongoDB Connection String

1. Log in to MongoDB Atlas: https://cloud.mongodb.com
2. Navigate to your cluster
3. Click "Connect" → "Drivers" → copy the connection string
4. Example format: `mongodb+srv://username:password@cluster0.xxxxx.mongodb.net/linkshare?retryWrites=true&w=majority`
5. **Save this** — you'll need it in Step 3

## Step 2: Sign Up to Render

1. Go to https://render.com
2. Click "Sign up"
3. Use GitHub to sign up (easier for linking your repo)
4. Verify email

## Step 3: Create a Web Service on Render

1. In Render dashboard, click **"New +"** → **"Web Service"**
2. Choose **"Deploy from a Git repository"**
3. Click **"Connect GitHub"** and authorize Render
4. Select repository: **Karankhandelwal2004/Linkshare**
5. Configure the service:
   - **Name**: `linkshare` (or your choice)
   - **Runtime**: Python 3 (auto-detected)
   - **Build Command**: (leave blank — Render will auto-detect)
   - **Start Command**: (leave blank — Render will use `Procfile`)
   - **Free tier** ✓ (or upgrade to paid)

   **Note:** Render automatically detects the `Procfile` in the repo root and uses it to run the service.

## Step 4: Set Environment Variables

Click **"Advanced"** and add the following **Environment Variables**:

| Key | Value |
|-----|-------|
| `MONGODB_URL` | Your MongoDB Atlas connection string from Step 1 |
| `SECRET_KEY` | Generate a random string (e.g., `python -c "import secrets; print(secrets.token_urlsafe(32))"`) |
| `ADMIN_PASSWORD` | Your admin password (e.g., `YourSecurePassword123!`) |

Example `MONGODB_URL`:
```
mongodb+srv://zberg1308_db_user:b1UnOtBJYWipRHv6@cluster0.ucd3te6.mongodb.net/linkshare?retryWrites=true&w=majority
```

Example `SECRET_KEY`:
```
kV8mF_2L9pQ-xJ_hN5K-sW3-qB7-vZ1
```

## Step 5: Deploy

1. Click **"Create Web Service"**
2. Render will automatically:
   - Clone your GitHub repo
   - Install dependencies from `requirements-lock.txt`
   - Start the app with uvicorn
3. Wait 2-5 minutes for deployment to complete
4. Check the **"Logs"** tab to see progress

## Step 6: Verify Deployment

Once deployment is done:

1. Click the URL provided by Render (e.g., `https://linkshare-xxxxx.onrender.com`)
2. You should see the login page
3. Try to register and login to test the app
4. Access admin panel: `https://linkshare-xxxxx.onrender.com/admin/login` (use your `ADMIN_PASSWORD`)

## Troubleshooting

### "Build failed"
- Check **Logs** for error messages
- Ensure `Code/requirements-lock.txt` exists in the repo
- Verify Python 3 runtime is selected

### "Application failed to start"
- Check **Logs** for the error
- Ensure `MONGODB_URL` is correct and MongoDB is running
- Verify environment variables are set

### "WebSocket connection failed"
- Render supports WebSockets — should work out of the box
- Check browser console (F12) for errors

### "Static files not found" (login.html, dashboard.html)
- Ensure `Code/public/` directory is pushed to GitHub
- Verify `Procfile` or startup command uses `cd Code &&` prefix

## Making Changes

After deployment, to push updates:

```bash
# Make changes locally
git add .
git commit -m "Your changes"
git push origin main

# Render will auto-redeploy (if auto-deploy is enabled)
# Check Render dashboard → Deployments tab
```

## Need Help?

- Render docs: https://render.com/docs
- FastAPI docs: https://fastapi.tiangolo.com
- MongoDB Atlas: https://docs.atlas.mongodb.com

## Optional: Custom Domain

1. In Render dashboard, go to **Settings** → **Custom Domain**
2. Add your domain and follow DNS setup instructions
3. SSL certificate auto-issued

---

**You're all set!** Your app is live on Render with WebSocket support and MongoDB.
