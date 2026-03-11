# SmartBinX: Revolutionizing E-Waste Management with Generative AI

SmartBinX is an AI-powered system designed to improve electronic waste management using deep learning and generative AI techniques. The project automatically classifies electronic waste from images and provides material composition insights to support sustainable recycling and responsible disposal.

## 📌 Project Overview

Electronic waste (E-waste) is one of the fastest-growing waste streams in the world. Improper disposal of electronic devices can lead to serious environmental and health problems due to toxic materials such as lead, mercury, and cadmium.

SmartBinX addresses this problem by using Artificial Intelligence to automatically identify and classify e-waste items. The system uses a Convolutional Neural Network (CNN) for image classification and provides additional insights about material composition for recycling purposes.

## 🚀 Features

- AI-based e-waste image classification
- Automated waste detection using deep learning
- Material composition analysis
- User-friendly web interface using Streamlit
- Real-time waste classification results
- Support for sustainable waste management

## 🛠 Technologies Used

- Python
- TensorFlow / Keras
- Streamlit
- OpenCV
- NumPy
- Pandas
- SQLite Database
- Machine Learning (CNN)

## ⚙️ System Workflow

1. User uploads an image of a waste item.
2. The image is preprocessed (resizing and normalization).
3. The trained CNN model classifies the waste.
4. If the item is identified as electronic waste, the system retrieves material composition data.
5. The result and material analysis are displayed through a Streamlit web interface.

## 📂 Project Structure

SmartBinX_Project
│
├── data/                # Dataset used for training
├── models/              # Trained machine learning models
├── notebooks/           # Jupyter notebooks for experiments
├── streamlit_app.py     # Streamlit web application
├── scraper_online.py    # Data scraping script
├── smartbinx_full.db    # SQLite database
├── requirements.txt     # Required Python libraries
└── README.md            # Project documentation
## ▶️ How to Run the Project

### 1️⃣ Clone the Repository

```bash
git clone https://github.com/yourusername/SmartBinX-Revolutionizing-EWaste-Management-Generative-AI.git

2️⃣ Install Required Libraries
pip install -r requirements.txt

3️⃣ Run the Streamlit Application
streamlit run streamlit_app.py

4️⃣ Upload Waste Image
Upload an image of a waste item and the system will classify it automatically.

📊 Results

The SmartBinX system successfully identifies electronic waste using image classification techniques. The AI model provides accurate predictions and additional insights about the material composition of electronic devices, helping improve recycling processes.

🔮 Future Scope
	•	Integration with IoT-based smart bins
	•	Mobile application development
	•	Cloud deployment
	•	Support for additional waste categories
	•	Improved model accuracy with larger datasets

👨‍💻 Authors
	•	Shashank S
	•	Adarsh Babasab Ugare
	•	Vaishak N Naik
	•	Harsha C R

B.E. Artificial Intelligence and Machine Learning
K.S. Institute of Technology, Bengaluru

📚 Academic Project

This project was developed as part of the Final Year Engineering Project (B.E. AIML).
