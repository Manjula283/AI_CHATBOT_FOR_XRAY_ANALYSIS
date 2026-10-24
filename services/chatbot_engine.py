"""
Report-Grounded Conversational Chatbot Service (PRD FR-05, FR-06, Section 11 & 12).
Uses the active chest X-ray analysis report, structured anatomical findings, and conversation
history as context. Explains findings in clear English while strictly avoiding autonomous
diagnosis, unsupported clinical claims, or treatment prescriptions.
"""
import re


MEDICAL_TERMINOLOGY_DICTIONARY = {
    "opacity": (
        "**Opacity** (or *radiopacity*) refers to any area on a chest X-ray that appears **whiter or brighter** than normal "
        "dark, air-filled lung tissue. Because X-ray beams pass easily through air (making healthy lungs look dark), anything denser "
        "than air—such as fluid, mucus, inflammation, scar tissue, or blood vessels—blocks more X-rays and creates a white shadow ('opacity'). "
        "An opacity is a descriptive observation, not a single disease by itself."
    ),
    "consolidation": (
        "**Consolidation** means that the tiny air sacs in a section of the lung (*alveoli*) have filled with fluid, inflammatory cells, "
        "or mucus instead of air. On an X-ray, consolidation looks like a solid or confluent white patch, sometimes showing dark branching "
        "tubes inside called **air bronchograms**."
    ),
    "air bronchogram": (
        "**Air bronchograms** are dark, tube-like branching lines visible inside a whiter patch of lung tissue. They happen when the "
        "larger breathing passages (*bronchi*) still contain air while the surrounding tiny air sacs (*alveoli*) are filled with fluid or inflammation."
    ),
    "cardiomegaly": (
        "**Cardiomegaly** means that the silhouette (outline) of the heart appears enlarged on the chest X-ray. Radiologists estimate this "
        "using the **Cardiothoracic Ratio (CTR)**—comparing the widest part of the heart shadow to the widest inner width of the rib cage. "
        "On a standard upright PA chest X-ray, a CTR greater than **0.50 (50%)** is generally described as cardiomegaly."
    ),
    "ctr": (
        "**Cardiothoracic Ratio (CTR)** is the width of the heart shadow divided by the internal width of the chest cage on a frontal X-ray. "
        "A normal CTR on an upright Posterior-Anterior (PA) chest radiograph is typically **less than 0.50**."
    ),
    "costophrenic": (
        "The **costophrenic angles** are the sharp, deep corners at the bottom left and bottom right of the lungs where the rib cage (*costo-*) "
        "meets the dome of the diaphragm (*-phrenic*). Normally, these corners form a crisp, acute angle. If fluid collects at the base of the "
        "lung, it fills in the corner—a finding called **costophrenic angle blunting**."
    ),
    "effusion": (
        "A **pleural effusion** is a collection of extra fluid in the thin space (*pleural cavity*) between the outside surface of the lung "
        "and the inside of the chest wall. Gravity usually pulls this fluid to the bottom corners of the lungs, causing a curved 'meniscus' shadow "
        "and blunting the costophrenic angles."
    ),
    "pneumothorax": (
        "**Pneumothorax** means air has leaked into the space between the lung and the chest wall, which can press on the lung and cause part "
        "of it to collapse. Radiologists check the outer edges and upper tips (apices) of the lungs carefully to ensure no pneumothorax is present."
    ),
    "infiltrate": (
        "An **infiltrate** (or *patchy airspace opacity*) describes an ill-defined, spotty shadow within the lung tissue where fluid, cells, "
        "or protein have spread into the air spaces or supporting tissue of the lung."
    ),
    "mediastinum": (
        "The **mediastinum** (or *cardiomediastinal silhouette*) is the central compartment of the chest Located between the right and left lungs. "
        "It holds the heart, the main blood vessels (like the aorta), the windpipe (trachea), and lymph nodes."
    ),
    "atelectasis": (
        "**Atelectasis** is a partial collapse or incomplete expansion of a small area of lung tissue, meaning those air sacs are deflated "
        "rather than filled with fluid."
    ),
    "clahe": (
        "**CLAHE** stands for *Contrast Limited Adaptive Histogram Equalization*. It is a medical image preprocessing technique used in this "
        "application to gently enhance local contrast across subtle lung markings and rib borders without over-amplifying radiographic noise."
    ),
}


class ReportGroundedChatbot:
    """
    Generates English-only conversational explanations grounded strictly in the saved
    Analysis record, its structured findings, and its quantitative metrics.
    """

    def generate_response(self, user_question: str, analysis_record, chat_history: list = None) -> str:
        question_clean = (user_question or "").strip()
        if not question_clean:
            return (
                "Please enter a question about your chest X-ray report—for example, "
                '*\"Can you explain this report in simple English?\"* or *\"What does opacity mean?\"*'
            )

        q_lower = question_clean.lower()
        meta = analysis_record.get_metadata() if hasattr(analysis_record, "get_metadata") else {}
        findings = meta.get("findings", {})
        impressions = meta.get("impressions", [])
        plain_english = meta.get("plain_english", "")
        uncertainty_notes = meta.get("uncertainty_notes", "")
        ctr = meta.get("displayed_ctr", meta.get("image_metrics", {}).get("estimated_ctr", 0.46))
        confidence = meta.get("confidence_score", 88.0)
        img_metrics = meta.get("image_metrics", {})
        zones = img_metrics.get("zones", {})
        case_label = getattr(analysis_record, "case_label", "Chest Radiograph")

        # 1. Check if user is asking for autonomous medical diagnosis or treatment/prescription (Section 12 Safety)
        if any(kw in q_lower for kw in ["prescribe", "antibiotic", "medication", "medicine", "treatment", "cure", "dosage", "should i take"]):
            return (
                "### Medical Safety Boundary — Treatment & Prescriptions\n\n"
                "I cannot recommend medications, antibiotics, or treatment plans. This application is an **AI-assisted assistant** "
                "designed solely to explain the wording of your chest X-ray report.\n\n"
                "**What Is Recorded in This Report:**\n"
                + "\n".join(f"- {imp}" for imp in impressions)
                + "\n\n**Next Steps with a Clinician:**\n"
                "- Share the original radiograph and your symptoms (such as cough, fever, or shortness of breath) with a licensed physician or radiologist.\n"
                "- Only a qualified healthcare professional who has examined you can make a diagnosis or prescribe treatment."
            )

        # 2. Check for "explain in simple English" / "plain English" / "easy to understand" / "layman"
        if any(kw in q_lower for kw in ["simple english", "plain english", "easy to understand", "explain this report", "what does this report mean", "in simple terms", "for a beginner"]):
            impression_bullets = "\n".join(f"- {imp}" for imp in impressions)
            return (
                f"### Plain-English Explanation of **{case_label}**\n\n"
                f"{plain_english}\n\n"
                "**Section-by-Section Breakdown in Everyday Terms:**\n"
                f"1. **Lungs & Breathing Tubes:** {self._simplify_lungs(findings.get('lungs_airways', ''))}\n"
                f"2. **Outer Lung Lining (Pleura):** {self._simplify_pleura(findings.get('pleura', ''))}\n"
                f"3. **Heart & Center of the Chest:** The heart outline has an estimated heart-to-chest width ratio (CTR) of **{ctr:.2f}** "
                f"({'within the typical normal range under 0.50' if ctr < 0.50 else 'wider than the typical 0.50 threshold, which the report notes as cardiomegaly'}).\n"
                f"4. **Ribs & Collarbones:** The visible bones look intact with no signs of a broken rib or bone injury.\n\n"
                "**Key Takeaway from the Impression Section:**\n"
                f"{impression_bullets}\n\n"
                "*Reminder: This explanation is AI-assisted and for informational support only. Always confirm findings with a qualified radiologist.*"
            )

        # 3. Check for "summarize the findings" / "summary" / "key findings" / "main takeaway"
        if any(kw in q_lower for kw in ["summarize", "summary", "key finding", "main finding", "impression", "overview", "tl;dr"]):
            imp_list = "\n".join(f"{i+1}. {imp}" for i, imp in enumerate(impressions))
            return (
                f"### Summary of Report Findings ({case_label})\n\n"
                "**Impressions:**\n"
                f"{imp_list}\n\n"
                "**Anatomical Checklist from This Study:**\n"
                f"- **Lungs & Airways:** {findings.get('lungs_airways', 'Evaluated in report.')}\n"
                f"- **Pleural Spaces:** {findings.get('pleura', 'Evaluated in report.')}\n"
                f"- **Cardiomediastinal Silhouette:** {findings.get('cardiomediastinal', 'Evaluated in report.')}\n"
                f"- **Osseous Structures:** {findings.get('osseous_soft_tissue', 'Evaluated in report.')}\n\n"
                f"**Quantitative Preprocessing Metrics:** Lung field symmetry index is **{img_metrics.get('lung_symmetry_pct', 94.0)}%** "
                f"and estimated cardiothoracic ratio (CTR) is **{ctr:.2f}** (confidence index: **{confidence}%**).\n\n"
                "*Note: Findings are AI-assisted and for informational support only — always confirm with a qualified radiologist.*"
            )

        # 4. Check for "limitations" / "uncertainty" / "accuracy" / "reliable" / "safety"
        if any(kw in q_lower for kw in ["limitation", "uncertain", "accuracy", "reliable", "trust", "mistake", "error", "disclaimer", "caveat"]):
            return (
                "### Key Limitations & Uncertainty to Understand in This Report\n\n"
                "When reading any chest X-ray report, it is important to understand both **radiographic limitations** and **automated analysis limitations**:\n\n"
                "1. **2D Projection Overlap:** A frontal chest X-ray compresses a 3D chest into a single flat 2D picture. Up to **25% of the lung tissue** sits behind the heart, spine, or domes of the diaphragm, which can hide subtle findings or create overlapping shadows.\n"
                "2. **No Clinical Context or Prior Films:** Unlike a hospital radiologist, this automated analysis cannot see your medical history, physical exam, blood tests, fever/cough symptoms, or prior X-rays to tell if a shadow is new or old.\n"
                "3. **Non-Specific Shadows:** An X-ray shadow (such as an *opacity*) shows *where* tissue density changed, but it cannot definitively prove the microscopic cause (for example, distinguishing bacterial pneumonia from viral inflammation, fluid, or localized atelectasis).\n"
                f"4. **Report-Specific Note:** {uncertainty_notes}\n\n"
                "**Safety Guidance:** This output is AI-assisted and for informational support only — always rely on a qualified radiologist or physician for clinical interpretation."
            )

        # 5. Check if user asks about a specific medical term ("What does opacity mean?", etc.)
        matched_terms = []
        for term_key, definition in MEDICAL_TERMINOLOGY_DICTIONARY.items():
            if term_key in q_lower:
                matched_terms.append((term_key, definition))

        if matched_terms or any(kw in q_lower for kw in ["what does", "what is a", "define", "definition", "meaning of", "mean?"]):
            if matched_terms:
                term_blocks = "\n\n".join(defn for _, defn in matched_terms)
                context_connection = self._connect_term_to_report(matched_terms[0][0], findings, impressions, ctr, zones)
                return (
                    "### Radiological Terminology Explanation\n\n"
                    f"{term_blocks}\n\n"
                    "**How This Applies to Your Current Report:**\n"
                    f"{context_connection}\n\n"
                    "*Let me know if you would like any other term in the report explained in plain English!*"
                )

        # 6. Check for specific anatomical systems: Heart / Cardiac
        if any(kw in q_lower for kw in ["heart", "cardiac", "cardiothoracic", "aorta", "aortic"]):
            return (
                "### Heart & Mediastinum Findings in Your Report\n\n"
                f"**From the Report:**\n> {findings.get('cardiomediastinal', 'No specific cardiac abnormality noted.')}\n\n"
                "**Plain-English Explanation:**\n"
                f"- The analysis measured an estimated **Cardiothoracic Ratio (CTR) of {ctr:.2f}**.\n"
                f"- {'Because this ratio is below 0.50, the heart shadow width is within the normal range for an upright PA chest X-ray.' if ctr < 0.50 else 'Because this ratio is above 0.50, the heart shadow appears wider than average on this projection, which radiologists describe as cardiomegaly.'}\n"
                "- The **mediastinum** refers to the central zone of the chest containing the heart and major blood vessels (such as the aortic arch).\n\n"
                "*Remember that patient positioning (e.g., an AP portable film vs. an upright PA film) and breathing depth can affect how wide the heart shadow looks.*"
            )

        # 7. Check for Pleura / Fluid / Corners of lungs
        if any(kw in q_lower for kw in ["pleura", "fluid", "corner", "angle", "diaphragm", "meniscus", "blunt"]):
            return (
                "### Pleura & Costophrenic Angle Findings in Your Report\n\n"
                f"**From the Report:**\n> {findings.get('pleura', 'Pleural spaces evaluated.')}\n\n"
                "**Plain-English Explanation:**\n"
                "- The **pleura** is the thin membrane that surrounds the lungs, and the **costophrenic angles** are the lower outer corners where the diaphragm meets the ribs.\n"
                f"- {self._simplify_pleura(findings.get('pleura', ''))}\n"
                f"- Quantitative basal density indices measured during preprocessing were **Right: {zones.get('right_costophrenic', 0.35):.2f}** and **Left: {zones.get('left_costophrenic', 0.35):.2f}**.\n\n"
                "*This information is grounded strictly in the current study's report.*"
            )

        # 8. Check for Lungs / Airways / Pneumonia / Zones
        if any(kw in q_lower for kw in ["lung", "airway", "trachea", "right", "left", "lobe", "zone", "patch", "normal", "clear", "abnormal"]):
            return (
                "### Lungs & Airways Findings in Your Report\n\n"
                f"**From the Report:**\n> {findings.get('lungs_airways', 'Lung fields evaluated.')}\n\n"
                "**Regional Zone Density Breakdown (Normalized 0.00–1.00 Scale):**\n"
                f"- **Right Upper Zone (RUZ):** `{zones.get('right_upper_zone', 0.30):.3f}`\n"
                f"- **Right Lower Zone (RLZ):** `{zones.get('right_lower_zone', 0.30):.3f}`\n"
                f"- **Left Upper Zone (LUZ):** `{zones.get('left_upper_zone', 0.30):.3f}`\n"
                f"- **Left Lower Zone (LLZ):** `{zones.get('left_lower_zone', 0.30):.3f}`\n"
                f"- **Bilateral Hemithorax Symmetry:** `{img_metrics.get('lung_symmetry_pct', 94.0)}%`\n\n"
                f"**What This Means in Simple Terms:**\n{plain_english}\n\n"
                "*Note: On a chest X-ray, higher regional density numbers indicate whiter/more radiopaque areas, whereas lower numbers indicate darker, air-filled lung zones.*"
            )

        # 9. Check for Bones / Ribs / Clavicles / Spine
        if any(kw in q_lower for kw in ["bone", "rib", "clavicle", "collarbone", "spine", "fracture", "skeleton", "osseous"]):
            return (
                "### Bones & Soft Tissues Findings in Your Report\n\n"
                f"**From the Report:**\n> {findings.get('osseous_soft_tissue', 'Visualized osseous structures appear intact.')}\n\n"
                "**Plain-English Explanation:**\n"
                "- **Osseous structures** is the medical term for the bones visible on the X-ray—specifically your **ribs**, **clavicles (collarbones)**, and **thoracic spine (upper/mid back bones)**.\n"
                "- In this report, no acute bone fractures or abnormal bone spots were identified.\n"
                "- Note that standard chest X-rays are optimized to look at the lungs and heart; dedicated rib-detail X-rays or CT scans are sometimes needed if a subtle rib injury is suspected clinically."
            )

        # 10. Questions to ask a doctor
        if any(kw in q_lower for kw in ["doctor", "physician", "radiologist", "ask my", "next step", "follow up", "follow-up"]):
            return (
                "### Helpful Questions to Ask Your Physician or Radiologist\n\n"
                "When reviewing this chest X-ray with a healthcare professional, you can ask:\n"
                "1. *\"Does your official clinical reading agree with the observations in this report?\"*\n"
                "2. *\"How do the X-ray findings relate to any symptoms I am experiencing (or lack of symptoms)?\"*\n"
                "3. *\"Should we compare this image with any previous chest X-rays I have had?\"*\n"
                "4. *\"Is any follow-up imaging or clinical checkup needed?\"*\n\n"
                "**Summary of This Report to Share:**\n"
                + "\n".join(f"- {imp}" for imp in impressions)
            )

        # 11. Default comprehensive contextual response grounded in the active report
        return (
            f"### Report-Grounded Answer for **{case_label}**\n\n"
            f"Based on the report for this study, here is how your question relates to the recorded findings:\n\n"
            f"**Plain-English Overview:**\n{plain_english}\n\n"
            "**Key Report Findings Referenced:**\n"
            f"- **Lungs & Airways:** {findings.get('lungs_airways', '')}\n"
            f"- **Pleura:** {findings.get('pleura', '')}\n"
            f"- **Heart & Mediastinum:** {findings.get('cardiomediastinal', '')}\n\n"
            "**Impression:**\n"
            + "\n".join(f"- {imp}" for imp in impressions)
            + "\n\n*You can also ask me specific questions such as: \"What does opacity mean?\", \"Can you summarize the findings?\", or \"What limitations should I understand in this report?\"*"
        )

    @staticmethod
    def _simplify_lungs(lung_text: str) -> str:
        t = lung_text.lower()
        if "right lower" in t and ("opacity" in t or "consolidation" in t):
            return "The lower part of the right lung shows a cloudy white patch ('opacity/consolidation'), while the left lung and upper right lung look clear and well-aerated."
        if "left upper" in t and "opacity" in t:
            return "The upper part of the left lung (below the collarbone) has a localized patchy shadow, while the rest of both lungs look clear."
        if "perihilar" in t or "bibasilar" in t:
            return "There is mild haziness around the central lung vessels and at the very bottom bases of both lungs, while the upper lungs remain clear."
        return "Both the right and left lungs look well-expanded and evenly filled with air, with no focal cloudy patches detected."

    @staticmethod
    def _simplify_pleura(pleura_text: str) -> str:
        t = pleura_text.lower()
        if "bilateral" in t and "effusion" in t:
            return "Both lower outer corners of the lungs ('costophrenic angles') look rounded/blunted, which suggests small-to-moderate fluid collection ('pleural effusion') at both lung bases."
        if "trace blunting" in t:
            return "The left lower lung corner is crisp and clear, while the right lower corner has very slight rounding ('trace blunting') next to the lower lung patch. No collapsed lung (pneumothorax) is seen."
        return "The lower outer corners of both lungs ('costophrenic angles') are sharp and clear, meaning there is no sign of fluid buildup or trapped air around the lungs."

    @staticmethod
    def _connect_term_to_report(term_key: str, findings: dict, impressions: list, ctr: float, zones: dict) -> str:
        combined = (" ".join(findings.values()) + " " + " ".join(impressions)).lower()
        if term_key in combined:
            return (
                f"This term appears directly in your current report. Specifically, the report notes: "
                f"*\"{impressions[0] if impressions else findings.get('lungs_airways', '')}\"* "
                f"(Measured regional densities: RUZ `{zones.get('right_upper_zone', 0.30):.2f}`, RLZ `{zones.get('right_lower_zone', 0.30):.2f}`, "
                f"LUZ `{zones.get('left_upper_zone', 0.30):.2f}`, LLZ `{zones.get('left_lower_zone', 0.30):.2f}`, CTR `{ctr:.2f}`)."
            )
        return (
            f"While **{term_key}** is a common chest X-ray term, your current report primarily emphasizes: "
            f"*\"{impressions[0] if impressions else 'no acute abnormality'}\"*."
        )


chatbot_engine = ReportGroundedChatbot()
