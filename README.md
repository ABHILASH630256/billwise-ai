<div align="center">

# 💸 BillWise AI

### 🤖 AI-Powered Smart Expense Tracker using OCR & Machine Learning

Automatically scan receipts, extract bill details using OCR, categorize expenses using Machine Learning, and visualize expenses through an interactive dashboard.

<p align="center">

<img src="https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white"/>
<img src="https://img.shields.io/badge/Flask-3.0-000000?style=for-the-badge&logo=flask"/>
<img src="https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white"/>
<img src="https://img.shields.io/badge/MySQL-4479A1?style=for-the-badge&logo=mysql&logoColor=white"/>
<img src="https://img.shields.io/badge/Render-46E3B7?style=for-the-badge&logo=render&logoColor=black"/>
<img src="https://img.shields.io/badge/OCR-Tesseract-green?style=for-the-badge"/>
<img src="https://img.shields.io/badge/Machine%20Learning-Scikit--Learn-orange?style=for-the-badge&logo=scikitlearn"/>

</p>

### 🌐 Live Demo

**https://billwise-ai-2.onrender.com**

</div>

---

# 📖 Overview

BillWise AI is a smart expense management system that simplifies bill tracking using Artificial Intelligence.

Instead of manually entering expense details, users can upload a receipt image and the application automatically:

- 📷 Scans the bill
- 🔍 Extracts text using OCR
- 🤖 Predicts expense category using Machine Learning
- 💱 Converts foreign currencies
- 💾 Stores expenses in a cloud database
- 📊 Displays analytics through an interactive dashboard

---

# ✨ Features

## 📷 OCR Bill Scanning

- Upload receipt images
- Automatic text extraction
- Merchant detection
- Bill amount detection
- Date extraction

---

## 🤖 Machine Learning

Automatically predicts categories like

- 🍔 Food
- 🛒 Grocery
- 🛍 Shopping
- 🚗 Transport
- 🏥 Healthcare
- 🎓 Education
- 🎬 Entertainment
- 💡 Utilities
- 🏨 Hotel
- 📦 Others

---

## 💱 Currency Conversion

- Detects multiple currencies
- Converts into preferred currency
- Real-time exchange rate support

---

## 📊 Dashboard

- Total expenses
- Recent bills
- Expense history
- Category analytics
- Spending summary

---

## 🔐 Authentication

- User Signup
- User Login
- Secure password hashing
- Session management

---

## ☁ Cloud Database

Stores all expenses securely using **Aiven Cloud MySQL**.

---

## 🐳 Docker Support

Containerized deployment using Docker and hosted on Render.

---

# 🚀 Live Demo

### 🔗 https://billwise-ai-2.onrender.com

---

# 🏗 System Architecture

```text
                User
                  │
                  ▼
          Upload Receipt
                  │
                  ▼
        Image Preprocessing
                  │
                  ▼
           OCR Extraction
                  │
                  ▼
     Merchant & Amount Detection
                  │
                  ▼
 Machine Learning Category Prediction
                  │
                  ▼
     Currency Conversion (Optional)
                  │
                  ▼
      Store in Cloud MySQL Database
                  │
                  ▼
 Dashboard • History • Analytics
```

---

# 🛠 Technology Stack

### Frontend

- HTML5
- CSS3
- JavaScript

### Backend

- Python
- Flask
- Gunicorn

### Machine Learning

- Scikit-Learn
- NumPy
- Joblib

### OCR

- Tesseract OCR
- OpenCV
- Pillow
- pytesseract

### Database

- MySQL
- Aiven Cloud

### Deployment

- Docker
- Render

---

# 📂 Project Structure

```text
BillWise-AI
│
├── backend
│   ├── app.py
│   ├── database.py
│   ├── predictor.py
│   ├── ocr.py
│   ├── advanced_apis.py
│   ├── requirements.txt
│   └── uploads
│
├── frontend
│   ├── index.html
│   ├── dashboard.html
│   ├── upload.html
│   ├── history.html
│   ├── login.html
│   ├── signup.html
│   ├── script.js
│   └── style.css
│
├── ml
│   ├── model.pkl
│   └── vectorizer.pkl
│
├── database
│
├── Dockerfile
│
└── README.md
```

---

# 📸 Screenshots

## 🏠 Home

![Home](Screenshots/home.png)

---

## 📤 Upload Bill

![Upload](Screenshots/upload.png)

---

## 📊 Dashboard

![Dashboard](Screenshots/dashboard.png)

---

## 📜 History

![History](Screenshots/history.png)

---

# ⚙ Installation

Clone the repository

```bash
git clone https://github.com/ABHILASH630256/billwise-ai.git
```

Move into the project

```bash
cd billwise-ai
```

Create virtual environment

```bash
python -m venv .venv
```

Activate

Windows

```bash
.venv\Scripts\activate
```

Linux / Mac

```bash
source .venv/bin/activate
```

Install dependencies

```bash
pip install -r backend/requirements.txt
```

Run

```bash
python backend/app.py
```

Open

```
http://localhost:5000
```

---

# 🐳 Docker

Build

```bash
docker build -t billwise-ai .
```

Run

```bash
docker run -p 10000:10000 billwise-ai
```

---

# 🌍 Deployment

- Docker
- Render
- Aiven Cloud MySQL

Live URL

**https://billwise-ai-2.onrender.com**

---

# 📈 Future Improvements

- 📱 Android Application
- 📄 PDF Receipt Support
- 🤖 AI Budget Recommendations
- 📧 Email Receipt Scanner
- 🎤 Voice Assistant
- 📊 Monthly Expense Prediction
- 🌙 Dark Mode
- 📥 Export Reports to Excel/PDF
- 🔔 Smart Spending Alerts

---

# 📊 Project Highlights

| Feature | Status |
|----------|--------|
| OCR Bill Scanning | ✅ |
| Machine Learning | ✅ |
| Currency Conversion | ✅ |
| User Authentication | ✅ |
| Expense Dashboard | ✅ |
| Docker Deployment | ✅ |
| Cloud Database | ✅ |
| Render Hosting | ✅ |

---

# 👨‍💻 Developer

## Abhilash Guda

🎓 Integrated M.Tech – Data Science

🏫 VIT Vellore

### GitHub

https://github.com/ABHILASH630256

### LinkedIn

*(Add your LinkedIn profile URL here.)*

---

# ⭐ Support

If you like this project,

⭐ Star this repository

🍴 Fork it

📢 Share it

---

# 📄 License

This project is created for educational, learning, and portfolio purposes.

© 2026 Abhilash Guda
