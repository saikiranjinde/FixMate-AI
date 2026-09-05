# FixMate-AI Firebase Website

This is a static Firebase Hosting site for the public FixMate-AI Windows app download.

## What is included

- Professional blue/cyan FixMate-AI website
- Download button for `public/downloads/FixMate-AI.exe`
- Download loading animation
- Thank-you popup after download click
- What it is / what it provides / why it is useful
- Download and usage steps
- Future scope
- Help modal:
  - Install/use steps
  - OpenRouter API key steps
  - Common error explanations
- About Us:
  - Created by: Saikiran Jinde
  - Email: saikiranjinde49@gmail.com
  - Version: 1.0.0

## Put the EXE on the site

Copy the final Windows executable into:

```text
public/downloads/FixMate-AI.exe
```

The website does not expose project source code to visitors. The public download is only the EXE.

## Firebase deploy

1. Install Node.js.
2. Install Firebase CLI:

```bash
npm install -g firebase-tools
```

3. Sign in:

```bash
firebase login
```

4. Put your Firebase project ID in `.firebaserc`.
5. From this folder:

```bash
firebase use YOUR_FIREBASE_PROJECT_ID
firebase deploy --only hosting
```

## Important

Do not put API keys, service-account JSON, or private credentials into `public/`.
