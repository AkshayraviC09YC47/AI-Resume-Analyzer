def ats_prompt(resume_text):
    return f"""
You are an ATS (Applicant Tracking System) resume analyzer.

Analyze the resume below and return the response strictly in the following format:

ATS Score: <0-100>

Strengths:
- point
- point

Weaknesses:
- point
- point

Missing Keywords:
- keyword
- keyword

Improvements:
- suggestion
- suggestion

Professional Summary (2 lines max)

Resume:
{resume_text}
"""
