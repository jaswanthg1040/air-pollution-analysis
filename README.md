# 🌍 Air Pollution Analysis

### A web-based platform for searching, analyzing, and visualizing air-quality data for different locations.

Air Pollution Analysis is a Flask-based web application that allows users to search for a location and view important air-quality parameters such as **AQI, PM2.5, NO₂, SO₂, and CO**.

The application retrieves air-quality data, stores relevant records in **PostgreSQL**, and presents the information through an interactive and user-friendly dashboard with charts and visualizations.

---

## 🚀 Features

### 🔎 Air Quality Search

- 🌍 Search air-quality information by location
- Retrieve air-quality data for the requested location
- Display the selected location and pollution information

### 📊 Pollution Information

The application displays:

- 🌍 **Air Quality Index (AQI)**
- 🌫️ **PM2.5**
- 🧪 **NO₂ (Nitrogen Dioxide)**
- 🧪 **SO₂ (Sulfur Dioxide)**
- 💨 **CO (Carbon Monoxide)**

All displayed pollution values are formatted to **one decimal place** for better readability.

### 📈 Data Visualization

- Interactive air-quality charts
- City-wise pollution analysis
- Pollution distribution visualization
- Graphical representation of collected data

### 🗄️ Data Storage

- PostgreSQL database integration
- Store air-quality records
- Retrieve previously stored records
- View historical pollution information

### 📥 Data Management

- Download available pollution data
- Work with collected air-quality records

### 🎨 User Interface

- Clean and responsive web interface
- 🌙 Light/Dark theme support
- Easy-to-use search interface
- Interactive data presentation

### ☁️ Deployment

- Vercel deployment configuration
- Production-ready Flask structure

---

## 🛠️ Technologies Used

| Category             | Technologies               |
| -------------------- | -------------------------- |
| **Backend**          | Python, Flask              |
| **Frontend**         | HTML, CSS, JavaScript      |
| **Database**         | PostgreSQL                 |
| **Air Quality Data** | Open-Meteo Air Quality API |
| **Visualization**    | Plotly                     |
| **Deployment**       | Vercel                     |
| **Version Control**  | Git, GitHub                |

---

## 🏗️ Project Architecture

```text
                    ┌──────────────────────┐
                    │        User          │
                    │  Searches Location   │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │    Web Interface     │
                    │    HTML / CSS / JS   │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │      Flask App       │
                    │       app.py         │
                    └──────────┬───────────┘
                               │
                  ┌────────────┴────────────┐
                  │                         │
                  ▼                         ▼
       ┌──────────────────┐       ┌──────────────────┐
       │ Open-Meteo API   │       │   PostgreSQL     │
       │ Air Quality Data │       │     Database     │
       └────────┬─────────┘       └────────┬─────────┘
                │                          │
                └────────────┬─────────────┘
                             ▼
                    ┌──────────────────────┐
                    │   Data Processing    │
                    │   & Visualization    │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │ Interactive Results  │
                    │ Charts & Records     │
                    └──────────────────────┘
```

---

## 📂 Project Structure

```text
air_pollution_analysis/
│
├── data/
│   └── Project data files
│
├── output/
│   └── Generated output files
│
├── static/
│   ├── style.css
│   └── script.js
│
├── templates/
│   └── index.html
│
├── .gitignore
├── LICENSE
├── app.py
├── requirements.txt
├── vercel.json
└── project-workspace.code-workspace
```

---

## ⚙️ How It Works

The application follows a simple data-processing workflow:

1. **User enters a location**
   - The user searches for a location through the web interface.

2. **Flask processes the request**
   - The backend receives and processes the search request.

3. **Air-quality data is retrieved**
   - The application obtains air-quality information through the Open-Meteo Air Quality API.

4. **Data is processed**
   - AQI and pollutant information is processed for presentation.

5. **Results are displayed**
   - The web interface displays the air-quality information.

6. **Records are stored**
   - Relevant information can be stored in PostgreSQL.

7. **Visualization**
   - Stored and retrieved information can be presented through charts and other visualizations.

---

## 📊 Air Quality Parameters

| Parameter | Description             |
| --------- | ----------------------- |
| **AQI**   | Air Quality Index       |
| **PM2.5** | Fine particulate matter |
| **NO₂**   | Nitrogen dioxide        |
| **SO₂**   | Sulfur dioxide          |
| **CO**    | Carbon monoxide         |

> 💡 Pollution values displayed in the application are formatted to **one decimal place** to make the results easier to read.

---

## 🗄️ Database

The application uses **PostgreSQL** to store air-quality records.

The database connection can be configured using either:

```text
POSTGRES_URL
```

or:

```text
DATABASE_URL
```

### Example

```text
POSTGRES_URL=your_postgresql_connection_string
```

### 🔐 Security

**Never commit your actual PostgreSQL connection string, password, API credentials, or other secrets to GitHub.**

Use environment variables instead.

---

## 🚀 Installation & Setup

### 1. Clone the Repository

```bash
git clone https://github.com/jaswanthg1040/air-pollution-analysis.git
```

### 2. Open the Project

```bash
cd air-pollution-analysis
```

### 3. Create a Virtual Environment

For Windows:

```bash
python -m venv venv
```

Activate it:

```bash
venv\Scripts\activate
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

### 5. Configure PostgreSQL

Set one of the following environment variables:

```text
POSTGRES_URL
```

or:

```text
DATABASE_URL
```

with your PostgreSQL connection string.

### 6. Run the Application

```bash
python app.py
```

The Flask server will start locally.

Open the local URL shown in your terminal in a web browser.

---

## 📈 Visualizations

The application provides interactive visualizations for understanding pollution data, including:

- 📊 City-wise pollution analysis
- 📉 Pollution distribution
- 📈 Air-quality comparisons
- 🌍 Location-based air-quality information

---

## 🖥️ Application Preview

The application provides an interactive dashboard for searching locations, viewing air-quality parameters, and analyzing pollution data through visualizations.

---

## ☁️ Deployment

The project includes a `vercel.json` configuration file for deployment using **Vercel**.

For deployment:

1. Connect the GitHub repository to Vercel.
2. Configure the required environment variables.
3. Configure the PostgreSQL database.
4. Deploy the application.

Make sure sensitive credentials are stored as environment variables rather than inside the source code.

---

## 🔮 Future Improvements

Possible future improvements include:

- 🌦️ Weather and air-quality correlation
- 📍 Interactive map-based pollution visualization
- 📱 Improved mobile interface
- 🔔 Air-quality alerts and notifications
- 📊 More advanced historical analysis
- 🤖 Machine-learning-based pollution prediction
- 🌐 Support for additional air-quality data sources

---

## 📄 License

This project is licensed under the **MIT License**.

See the [LICENSE](LICENSE) file for more information.

---

## 👨‍💻 Author

### Jaswanth Reddy

GitHub: [@jaswanthg1040](https://github.com/jaswanthg1040)

---

## ⭐ Support

If you find this project useful or interesting, consider giving the repository a ⭐ on GitHub.

It helps support the project and makes it easier for others to discover it.

---

## 🔗 Repository

[Air Pollution Analysis](https://github.com/jaswanthg1040/air-pollution-analysis)
