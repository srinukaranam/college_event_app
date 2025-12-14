# 🎓 College Event Management System  
A complete event management platform built using **Flask**, **SQLite**, **HTML**, **CSS**, and **JavaScript**.  
This system allows students to browse events, register, get QR codes, and check attendance.  
Admins can manage events, view registrations, track attendance, and export reports (Excel, PDF, CSV).

---

## 🚀 Features

### 👨‍🎓 Student Features
- Register & Login  
- View available events  
- Register for an event  
- Auto-generated QR code for each registration  
- View your registered events  
- Mobile-friendly UI  
- Installable as a PWA (Progressive Web App)

### 🧑‍🏫 Staff Features
- Staff login  
- QR code scanning & verification  
- Attendance marking  
- View check-in history  

### 🛠️ Admin Features
- Admin login  
- Create / Edit / Delete events  
- View event registrations  
- Mark attendance manually  
- Export:
  - ✔ Excel (.xlsx)
  - ✔ PDF
  - ✔ CSV  
- View dashboard stats (events, students, registrations)  
- Recent attendance logs

---

## 🗂️ Tech Stack

| Layer | Technology |
|------|------------|
| Backend | Python Flask |
| Database | PostgreSQL |
| Frontend | HTML, CSS, JavaScript, Bootstrap |
| QR Code | `qrcode` Python library |
| Export | Pandas, OpenPyXL, ReportLab |
| Mobile App Support | PWA (service worker + manifest) |

---

## 📦 Installation

### 1️⃣ Clone the Repository
```bash
git clone https://github.com/YOUR_USERNAME/college-event-app.git
cd college-event-app
