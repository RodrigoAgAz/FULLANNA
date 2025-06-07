"""
medical_info_templates.py

This module provides accurate, structured templates for common medical conditions
and questions. These templates ensure consistency, accuracy, and completeness
in ANNA's responses to frequently asked medical questions.
"""

# DIABETES INFORMATION TEMPLATE
# Addresses issue #1: Topic mismatch in diabetes response
DIABETES_INFO = {
    "brief_answer": "Diabetes is a chronic condition that affects how your body processes blood sugar (glucose). Common symptoms include increased thirst, frequent urination, unexplained weight loss, fatigue, blurred vision, slow-healing sores, and frequent infections.",
    
    "detailed_info": {
        "COMMON SYMPTOMS": [
            "Increased thirst and frequent urination", 
            "Extreme hunger", 
            "Unexplained weight loss",
            "Fatigue and weakness",
            "Blurred vision",
            "Slow-healing sores or frequent infections",
            "Tingling or numbness in hands/feet (more common in type 2)"
        ],
        
        "TYPE 1 VS TYPE 2": [
            "Type 1: Symptoms often develop quickly (days to weeks) and can be severe",
            "Type 2: Symptoms typically develop gradually and may be mild or absent initially",
            "Gestational: Often asymptomatic, detected through screening tests during pregnancy"
        ],
        
        "RISK FACTORS": [
            "Type 1: Family history, genetics, certain viruses may trigger onset",
            "Type 2: Overweight, physical inactivity, family history, age (over 45), ethnicity",
            "Gestational: Previous gestational diabetes, family history, obesity, older maternal age"
        ]
    },
    
    "emergency_symptoms": [
        "Extreme thirst and very frequent urination",
        "Severe nausea and vomiting",
        "Breath that smells fruity or like acetone",
        "Confusion or loss of consciousness",
        "Severe abdominal pain"
    ],
    
    "when_to_see_doctor": [
        "If you experience multiple symptoms listed above",
        "If you have risk factors for diabetes",
        "For routine screening, especially if you're over 45"
    ],
    
    "prevention": [
        "Maintain a healthy weight",
        "Be physically active for at least 30 minutes most days",
        "Eat a balanced diet rich in fruits, vegetables, and whole grains",
        "Limit processed foods and added sugars",
        "Get regular check-ups and screenings"
    ]
}

# BLOOD PRESSURE INFORMATION TEMPLATE
# Addresses issues #1 and #9: Provide comprehensive information with normal ranges
BLOOD_PRESSURE_INFO = {
    "brief_answer": "Blood pressure is the force of blood pushing against the walls of your arteries. High blood pressure (hypertension) often has no symptoms, which is why it's called the 'silent killer.' The only reliable way to know if you have high blood pressure is to have it measured.",
    
    "detailed_info": {
        "HOW TO CHECK": [
            "Have your blood pressure measured by a healthcare professional",
            "Use a home blood pressure monitor (available at most pharmacies)",
            "Public blood pressure machines (in some pharmacies and stores)",
            "Take multiple readings at different times for accuracy"
        ],
        
        "UNDERSTANDING READINGS": [
            "Blood pressure is recorded as two numbers: systolic/diastolic",
            "Systolic (top number): Pressure when heart beats",
            "Diastolic (bottom number): Pressure when heart rests between beats"
        ],
        
        "RISK FACTORS": [
            "Family history of high blood pressure",
            "Age (risk increases as you get older)",
            "Race (more common in African Americans)",
            "Obesity or being overweight",
            "Physical inactivity",
            "High sodium diet",
            "Excessive alcohol consumption",
            "Stress",
            "Certain chronic conditions (diabetes, kidney disease)"
        ]
    },
    
    "normal_values": {
        "Normal": {"range": "Below 120/80 mmHg"},
        "Elevated": {"range": "120-129/<80 mmHg", "note": "Risk of developing high blood pressure without intervention"},
        "Stage 1 Hypertension": {"range": "130-139/80-89 mmHg", "note": "Lifestyle changes typically recommended, medication may be considered"},
        "Stage 2 Hypertension": {"range": "140+/90+ mmHg", "note": "Likely to need medication along with lifestyle changes"},
        "Hypertensive Crisis": {"range": "Higher than 180/120 mmHg", "note": "EMERGENCY - Requires immediate medical attention"}
    },
    
    "when_to_see_doctor": [
        "Blood pressure consistently above 130/80 mmHg",
        "Symptoms like headaches, vision changes, chest pain with high readings",
        "To develop a comprehensive plan addressing blood pressure"
    ],
    
    "practical_steps": [
        "Reduce sodium intake (processed foods, restaurant meals)",
        "Follow the DASH diet (rich in fruits, vegetables, whole grains)",
        "Regular physical activity (at least 150 minutes/week)",
        "Maintain a healthy weight",
        "Limit alcohol consumption",
        "Quit smoking",
        "Manage stress through relaxation techniques"
    ]
}

# COLD VS. FLU INFORMATION TEMPLATE
# Addresses issue #4: Condition variants clarification
COLD_VS_FLU_INFO = {
    "brief_answer": "Colds and flu are both respiratory infections caused by different viruses. The flu tends to be more severe with a sudden onset, while colds generally develop more gradually and are milder. Understanding the differences can help determine appropriate care.",
    
    "variants": {
        "COLD": {
            "description": "Common colds are mild viral infections primarily affecting the nose and throat.",
            "symptoms": [
                "Gradual onset over several days",
                "Mild to moderate symptoms",
                "Runny or stuffy nose (main symptom)",
                "Sneezing and sore throat are common",
                "Mild cough",
                "Rarely causes fever in adults (slight fever possible in children)",
                "Rarely causes significant fatigue or body aches",
                "Typically does not cause headaches",
                "Does not usually result in serious health problems"
            ],
            "treatment": [
                "Rest and hydration",
                "Over-the-counter cold medications for symptom relief",
                "Saline nasal spray",
                "Humidifier to ease congestion",
                "Typically resolves in 7-10 days"
            ]
        },
        "FLU": {
            "description": "Influenza (flu) is a more severe viral infection that affects the respiratory system and can impact the whole body.",
            "symptoms": [
                "Rapid onset (can develop within hours)",
                "Moderate to severe symptoms",
                "Fever, usually high (100°F-104°F), lasting 3-4 days",
                "Prominent fatigue and weakness (can last up to 2-3 weeks)",
                "Severe body aches and headaches",
                "Dry cough",
                "Chills",
                "Less prominent nasal symptoms compared to colds",
                "Can lead to complications like pneumonia"
            ],
            "treatment": [
                "Rest and hydration",
                "Antiviral medications if started within 48 hours of symptoms",
                "Over-the-counter medications for fever and pain",
                "Typically improves within 1-2 weeks",
                "May require medical attention for severe cases"
            ]
        }
    },
    
    "when_to_see_doctor": [
        "Difficulty breathing or shortness of breath",
        "Persistent chest or abdominal pain",
        "Persistent dizziness or confusion",
        "Seizures",
        "Severe muscle pain",
        "Severe weakness or unsteadiness",
        "Fever or cough that improves then returns worse",
        "Worsening of chronic medical conditions"
    ],
    
    "prevention": [
        "Annual flu vaccination",
        "Frequent handwashing with soap and water",
        "Avoid close contact with sick individuals",
        "Cover coughs and sneezes with tissues or your elbow",
        "Clean and disinfect frequently touched surfaces",
        "Avoid touching your face"
    ]
}

# CHEST PAIN INFORMATION TEMPLATE
# Addresses issue #10: Clear emergency information
CHEST_PAIN_INFO = {
    "brief_answer": "Chest pain can have many different causes ranging from non-life-threatening conditions to serious medical emergencies like heart attacks. Because chest pain can be a sign of a serious problem, it's important to seek immediate medical care if you experience certain warning signs.",
    
    "detailed_info": {
        "EMERGENCY SIGNS (CALL 911/EMERGENCY SERVICES)": [
            "Pressure, squeezing, or fullness in the center of your chest lasting more than a few minutes or that comes and goes",
            "Pain spreading to shoulders, arms, neck, jaw, or back",
            "Cold sweat, nausea, or lightheadedness accompanying chest pain",
            "Shortness of breath with or without chest discomfort",
            "Sudden severe chest pain with palpitations and anxiety"
        ],
        
        "NON-EMERGENCY CHEST PAIN THAT STILL REQUIRES MEDICAL ATTENTION": [
            "Sharp pain that worsens when breathing deeply or coughing (may indicate lung issues)",
            "Tenderness when pressing on the chest wall",
            "Pain that improves or worsens when changing positions",
            "Persistent mild to moderate chest pain",
            "Chest pain with fever and cough"
        ],
        
        "POSSIBLE CAUSES OF CHEST PAIN": [
            "Heart-related: Heart attack, angina, myocarditis, pericarditis",
            "Lung-related: Pulmonary embolism, pneumonia, pleurisy, pneumothorax, asthma",
            "Digestive: Acid reflux (GERD), esophageal spasm, gallbladder issues, pancreatitis",
            "Musculoskeletal: Costochondritis, sore muscles, injured ribs",
            "Other: Panic attack, shingles, severe anxiety"
        ]
    },
    
    "emergency_symptoms": [
        "Crushing, squeezing pressure or tightness in chest",
        "Chest pain spreading to jaw, neck, shoulder, arm, or back",
        "Chest pain accompanied by shortness of breath, sweating, dizziness, or nausea",
        "Sudden, sharp chest pain with shortness of breath, especially after long periods of inactivity",
        "Very rapid or irregular heartbeat with chest pain"
    ],
    
    "when_to_see_doctor": [
        "Chest pain that's not going away and you're not sure if it's an emergency",
        "Recurring chest pain triggered by exertion",
        "Persistent chest discomfort of any kind",
        "Chest pain that concerns you, even if standard tests come back normal"
    ],
    
    "practical_steps": [
        "For emergency symptoms, call 911 or local emergency number immediately",
        "For non-emergency chest pain, record when it occurs and what makes it better or worse",
        "Note related symptoms (like coughing or anxiety)",
        "Don't ignore chest pain and hope it goes away",
        "Don't diagnose yourself - seek professional evaluation"
    ]
}

# SPRAINED ANKLE INFORMATION TEMPLATE
# Addresses issues #3 and #6: Detailed home care instructions
SPRAINED_ANKLE_INFO = {
    "brief_answer": "A sprained ankle occurs when the ligaments that connect the bones at the ankle joint are stretched or torn. Treatment involves rest, ice, compression, and elevation, along with proper rehabilitation to prevent future sprains.",
    
    "detailed_info": {
        "IMMEDIATE TREATMENT (FIRST 24-72 HOURS)": [
            "Rest: Avoid putting weight on the injured ankle",
            "Ice: Apply ice for 15-20 minutes every 2-3 hours to reduce swelling",
            "Compression: Use an elastic bandage to support the ankle and reduce swelling",
            "Elevation: Keep your ankle raised above the level of your heart when possible"
        ],
        
        "GRADES OF ANKLE SPRAINS": [
            "Grade 1 (Mild): Minimal pain, swelling, and no joint instability",
            "Grade 2 (Moderate): Moderate pain, swelling, and some joint looseness",
            "Grade 3 (Severe): Significant pain, swelling, and joint instability"
        ],
        
        "RECOVERY PHASE (AFTER INITIAL SWELLING SUBSIDES)": [
            "Begin gentle range-of-motion exercises (ankle circles, flexing and pointing)",
            "Gradually increase weight-bearing as tolerated",
            "Use supportive footwear when walking",
            "Consider physical therapy for moderate to severe sprains",
            "Use of assistive devices (crutches, walking boot) as recommended by healthcare provider"
        ]
    },
    
    "when_to_see_doctor": [
        "Inability to bear weight on the affected foot",
        "Severe swelling or bruising",
        "Pain directly over the ankle bones",
        "Heard or felt a 'pop' at the time of injury",
        "Pain and swelling don't improve after several days of home treatment"
    ],
    
    "practical_steps": [
        "Properly wrap the ankle with an elastic bandage (not too tight)",
        "Keep ice in a cloth (never apply directly to skin)",
        "Take over-the-counter pain relievers as directed for pain",
        "Use crutches if needed to avoid bearing weight",
        "Begin rehabilitation exercises only when recommended"
    ],
    
    "prevention": [
        "Warm up before physical activity",
        "Use supportive shoes appropriate for your activity",
        "Gradually increase exercise intensity",
        "Improve balance and strength with ankle exercises",
        "Consider ankle braces for high-risk activities if you have previous sprains"
    ]
}

# CHOLESTEROL INFORMATION TEMPLATE
# Addresses issue #4: Complete medical information with normal ranges
CHOLESTEROL_INFO = {
    "brief_answer": "Cholesterol is a waxy, fat-like substance found in all cells of the body. Your body needs cholesterol to make hormones, vitamin D, and substances that help digest foods. While your body makes all the cholesterol it needs, it's also found in foods from animal sources.",
    
    "detailed_info": {
        "TYPES OF CHOLESTEROL": [
            "LDL (Low-Density Lipoprotein): Often called 'bad' cholesterol; can build up on artery walls",
            "HDL (High-Density Lipoprotein): Known as 'good' cholesterol; helps remove LDL from arteries",
            "Triglycerides: Another type of fat in the blood; high levels increase heart disease risk",
            "Total cholesterol: The overall amount of cholesterol in your blood"
        ],
        
        "HOW CHOLESTEROL AFFECTS HEALTH": [
            "High LDL increases risk of heart disease and stroke",
            "Low HDL also increases cardiovascular risk",
            "Total cholesterol gives an overall picture but isn't as informative as the breakdown",
            "The ratio of total cholesterol to HDL can be a useful measure of risk"
        ],
        
        "FACTORS THAT AFFECT CHOLESTEROL LEVELS": [
            "Diet high in saturated and trans fats",
            "Lack of physical activity",
            "Obesity or overweight",
            "Smoking",
            "Age and gender",
            "Genetics and family history",
            "Certain medical conditions (diabetes, hypothyroidism)"
        ]
    },
    
    "normal_values": {
        "Total Cholesterol": {"normal": "Below 200 mg/dL", "abnormal": "Borderline high: 200-239 mg/dL, High: 240 mg/dL and above"},
        "LDL Cholesterol": {"normal": "Below 100 mg/dL", "abnormal": "Near optimal: 100-129 mg/dL, Borderline high: 130-159 mg/dL, High: 160-189 mg/dL, Very high: 190 mg/dL and above"},
        "HDL Cholesterol": {"normal": "60 mg/dL and above (higher is better)", "abnormal": "Low: Below 40 mg/dL for men, Below 50 mg/dL for women"},
        "Triglycerides": {"normal": "Below 150 mg/dL", "abnormal": "Borderline high: 150-199 mg/dL, High: 200-499 mg/dL, Very high: 500 mg/dL and above"}
    },
    
    "when_to_see_doctor": [
        "For regular cholesterol screening (every 4-6 years for adults, more frequently with risk factors)",
        "If you have a family history of high cholesterol or heart disease",
        "If you have other risk factors like diabetes, high blood pressure, or smoking",
        "If you're on cholesterol-lowering medication, for monitoring"
    ],
    
    "practical_steps": [
        "Eat a heart-healthy diet (limit saturated fats, eliminate trans fats, increase fiber)",
        "Exercise regularly (aim for at least 150 minutes of moderate activity weekly)",
        "Maintain a healthy weight",
        "Quit smoking",
        "Limit alcohol consumption"
    ]
}

# COLONOSCOPY INFORMATION TEMPLATE
COLONOSCOPY_INFO = {
    "brief_answer": "A colonoscopy is a procedure that lets doctors examine the inner lining of your large intestine (colon and rectum) using a flexible tube with a camera. It's primarily used to screen for colorectal cancer and find or remove polyps before they become cancerous.",
    
    "detailed_info": {
        "WHAT IS A COLONOSCOPY": [
            "An examination procedure using a colonoscope (long, flexible tube with a camera and light source)",
            "Allows doctors to view the entire colon and rectum",
            "Usually lasts 30-60 minutes",
            "Performed under mild sedation so patients are comfortable"
        ],
        
        "WHY IT IS DONE": [
            "Screens for colorectal cancer (the third most common cancer)",
            "Detects and removes precancerous polyps before they become malignant",
            "Investigates unexplained changes in bowel habits or abdominal symptoms",
            "Evaluates inflammatory bowel disease, bleeding, or other abnormalities",
            "Follow-up examination after previous findings"
        ],
        
        "WHAT TO EXPECT": [
            "Bowel prep required the day before (clear liquids and laxative solution)",
            "You'll receive sedation through an IV before the procedure",
            "The doctor gently inserts the colonoscope through the rectum",
            "Air or carbon dioxide inflates the colon for better viewing",
            "If polyps are found, they can typically be removed during the procedure",
            "Recovery usually takes about 1-2 hours after the procedure",
            "You'll need someone to drive you home due to the sedation"
        ],
        
        "WHEN IS IT RECOMMENDED": [
            "Average-risk adults should begin screening at age 45",
            "If you have a family history of colorectal cancer, screenings may start earlier",
            "Typically repeated every 10 years if normal and you have average risk",
            "More frequent follow-ups if polyps are found or you have other risk factors"
        ]
    },
    
    "when_to_see_doctor": [
        "Follow your doctor's recommendations for screening based on your risk factors",
        "If you experience unexplained abdominal pain, blood in stool, or changes in bowel habits",
        "If you have a family history of colorectal cancer or polyps"
    ],
    
    "practical_steps": [
        "Follow bowel prep instructions exactly - clean colon is essential for effective screening",
        "Arrange for someone to drive you home after the procedure",
        "Take the day off work on the day of the procedure",
        "Discuss any medications you're taking with your doctor before the procedure",
        "After the procedure, you may experience some bloating or gas pain, which is normal"
    ]
}

# Add more templates as needed...

# Dictionary of templates by topic for easy lookup
MEDICAL_INFO_TEMPLATES = {
    "diabetes": DIABETES_INFO,
    "blood pressure": BLOOD_PRESSURE_INFO,
    "hypertension": BLOOD_PRESSURE_INFO,
    "cold vs flu": COLD_VS_FLU_INFO,
    "chest pain": CHEST_PAIN_INFO,
    "sprained ankle": SPRAINED_ANKLE_INFO,
    "cholesterol": CHOLESTEROL_INFO,
    "colonoscopy": COLONOSCOPY_INFO,
}

def get_template_for_topic(topic: str):
    """
    Get the appropriate template for a given medical topic.
    Returns None if no specific template is available.
    """
    topic_lower = topic.lower()
    
    # Direct match
    if topic_lower in MEDICAL_INFO_TEMPLATES:
        return MEDICAL_INFO_TEMPLATES[topic_lower]
    
    # Partial match
    for key in MEDICAL_INFO_TEMPLATES:
        if key in topic_lower or topic_lower in key:
            return MEDICAL_INFO_TEMPLATES[key]
    
    # No match
    return None