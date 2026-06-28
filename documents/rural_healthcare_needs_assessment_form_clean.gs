/**
 * Rural Healthcare Clinic Needs Assessment Questionnaire
 * Google Apps Script / Google Forms builder
 *
 * How to use:
 * 1. Go to https://script.google.com and create a new Apps Script project.
 * 2. Paste this file into Code.gs.
 * 3. Run createRuralHealthcareClinicNeedsAssessmentForm().
 * 4. Authorize the script.
 * 5. Open View > Logs to find the edit URL and live form URL.
 *
 * Notes:
 * - No questions are required. Respondents may skip any question.
 * - Closed-ended questions include N/A, Not sure, or Prefer not to answer where appropriate.
 * - Google Forms cannot create a true table with rating columns plus free-text comment cells.
 *   Section B uses a multiple-choice grid for the 1-5/N/A ratings and a separate comment field.
 */

function createRuralHealthcareClinicNeedsAssessmentForm() {
  const form = FormApp.create('Rural Healthcare Clinic Needs Assessment Questionnaire');

  form.setDescription([
    'Purpose: This questionnaire is designed to help identify the operational, clinical, financial, compliance, workforce, technology, and community-health needs of rural healthcare clinics. The results will be used to understand clinic priorities and guide the development of services, tools, analytics, training, or other support that may better fit rural clinic needs.',
    'Who should complete this: Clinic administrator, practice manager, clinical lead, billing/revenue-cycle lead, or another staff member familiar with clinic operations. If possible, complete this with input from clinical, administrative, billing, and technology staff.',
    'Estimated time: 15-20 minutes.',
    'Please answer the questions that apply to your clinic. You may select N/A, Not sure, Prefer not to answer, or skip any question.',
    'Confidentiality note: Please do not include patient names, medical record numbers, or other individually identifiable patient information.'
  ].join('\n\n'));

  form.setCollectEmail(false);
  form.setAllowResponseEdits(true);
  form.setProgressBar(true);
  form.setConfirmationMessage('Thank you for your time and feedback.');

  addSectionHeader_(form, 'Section A. Clinic Profile');
  addSectionA_(form);
  addSectionB_(form);
  addSectionC_(form);
  addSectionD_(form);
  addSectionE_(form);
  addSectionF_(form);
  addSectionG_(form);
  addSectionH_(form);
  addSectionI_(form);
  addSectionJ_(form);
  addSectionK_(form);

  Logger.log('Form edit URL: ' + form.getEditUrl());
  Logger.log('Live form URL: ' + form.getPublishedUrl());

  return form;
}

function addSectionA_(form) {
  addMultipleChoice_(form, '1. What is your role at the clinic?', [
    'Owner/CEO/Executive Director',
    'Clinic Administrator/Practice Manager',
    'Physician/Medical Director',
    'Nurse Practitioner/Physician Assistant/CNM',
    'Nurse/MA/Clinical Staff',
    'Billing/Revenue Cycle',
    'IT/EHR/Data',
    'Other',
    'Prefer not to answer'
  ]);

  addMultipleChoice_(form, '2. What type of clinic best describes your organization?', [
    'Independent Rural Health Clinic',
    'Provider-Based Rural Health Clinic',
    'Federally Qualified Health Center or FQHC look-alike',
    'Critical Access Hospital-affiliated clinic',
    'Private primary care clinic serving rural patients',
    'Other',
    'Not sure',
    'N/A'
  ]);

  addMultipleChoice_(form, '3. How many physical clinic sites do you operate?', [
    '1',
    '2-3',
    '4-5',
    'More than 5',
    'Not sure',
    'N/A'
  ]);

  addText_(form, '4a. Primary clinic/site name');
  addText_(form, '4b. Primary clinic street address');
  addText_(form, '4c. Primary clinic city');
  addText_(form, '4d. Primary clinic state');
  addText_(form, '4e. Primary clinic ZIP code');
  addText_(form, '4f. Primary clinic county');
  addParagraph_(form, '4g. Additional clinic site addresses, including county', 'If your organization operates multiple sites, list each site separately using this format: site name; street address; city, state, ZIP; county.');

  addMultipleChoice_(form, '5. Approximately how many patient visits does your clinic handle per year?', [
    'Fewer than 2,500',
    '2,500-5,000',
    '5,001-10,000',
    '10,001-25,000',
    'More than 25,000',
    'Not sure',
    'N/A'
  ]);

  addCheckboxes_(form, '6. Which populations does your clinic primarily serve? Check all that apply.', [
    'Medicare patients',
    'Medicaid patients',
    'Commercially insured patients',
    'Uninsured or self-pay patients',
    'Older adults',
    'Children/families',
    'Agricultural or seasonal workers',
    'Veterans',
    'Patients with limited transportation access',
    'Patients with behavioral health or substance-use needs',
    'Other',
    'Not sure',
    'N/A'
  ]);

  addText_(form, '7. What EHR or practice management system do you currently use?');
}

function addSectionB_(form) {
  addPage_(form, 'Section B. Top Needs and Priorities');

  addText_(form, '8a. Biggest challenge #1', 'Please list up to three.');
  addText_(form, '8b. Biggest challenge #2');
  addText_(form, '8c. Biggest challenge #3');

  const ratingAreas = [
    'Staffing and workforce capacity',
    'Provider recruitment and retention',
    'Patient access and appointment availability',
    'Telehealth or virtual care',
    'Behavioral health access',
    'Chronic disease management',
    'Preventive care and screenings',
    'Care coordination and referrals',
    'Social determinants of health / social needs',
    'Billing, coding, and reimbursement',
    'Denials, claim errors, or revenue leakage',
    'Compliance with CMS/RHC/HIPAA/HRSA requirements',
    'Quality reporting and performance measurement',
    'Data dashboards and analytics',
    'EHR optimization and workflow automation',
    'Cybersecurity and privacy',
    'Grant readiness and funding support',
    'Emergency preparedness and public health response',
    'Staff training',
    'Patient education',
    'Technology training'
  ];

  form.addGridItem()
    .setTitle('9. Please rate the current level of need in each area.')
    .setHelpText('Rating scale: 1 = No major need; 2 = Minor need; 3 = Moderate need; 4 = Significant need; 5 = Critical need; N/A = Not applicable or not sure.')
    .setRows(ratingAreas)
    .setColumns(['1', '2', '3', '4', '5', 'N/A'])
    .setRequired(false);

  addParagraph_(form, '9a. Brief comments on any ratings above', 'Use this space to explain any ratings as needed.');

  addText_(form, '10a. External help priority #1', 'Of the areas above, list up to five where you would most want external help over the next 6-12 months.');
  addText_(form, '10b. External help priority #2');
  addText_(form, '10c. External help priority #3');
  addText_(form, '10d. External help priority #4');
  addText_(form, '10e. External help priority #5');
}

function addSectionC_(form) {
  addPage_(form, 'Section C. Patient Access and Community Needs');

  addMultipleChoice_(form, '11. How would you describe current patient access to primary care appointments?', [
    'Meets patient need',
    'Some delays, but manageable',
    'Significant delays',
    'Severe access problem',
    'Not sure',
    'N/A'
  ]);

  addMultipleChoice_(form, '12. What is the approximate wait time for a routine primary care appointment?', [
    'Same day/next day',
    '2-7 days',
    '1-2 weeks',
    '3-4 weeks',
    'More than 1 month',
    'Not sure',
    'N/A'
  ]);

  addCheckboxes_(form, '13. What access barriers are most common for your patients? Check all that apply.', [
    'Transportation',
    'Cost of care',
    'Lack of insurance or underinsurance',
    'Limited clinic hours',
    'Difficulty getting specialist referrals',
    'Limited broadband or technology access',
    'Language or health literacy barriers',
    'Childcare or work-schedule barriers',
    'Behavioral health access',
    'Medication affordability',
    'Other',
    'Not sure',
    'N/A'
  ]);

  addCheckboxes_(form, '14. Which services are most needed but difficult for your patients to access? Check all that apply.', [
    'Primary care',
    'Urgent care / same-day care',
    'Behavioral health',
    'Substance-use treatment',
    'Dental care',
    'Women\'s health',
    'Pediatric care',
    'Chronic disease management',
    'Diabetes education',
    'Nutrition support',
    'Transportation support',
    'Specialty care',
    'Diagnostic testing or labs',
    'Pharmacy access',
    'Other',
    'Not sure',
    'N/A'
  ]);

  addCheckboxes_(form, '15. Which community-level issues most affect patient health in your service area? Check all that apply.', [
    'Food insecurity',
    'Housing instability',
    'Utility insecurity',
    'Transportation barriers',
    'Poverty or unemployment',
    'Social isolation',
    'Low health literacy',
    'Limited broadband/internet access',
    'Substance use',
    'Mental health needs',
    'Domestic violence or interpersonal safety concerns',
    'Disability-related access barriers',
    'Other',
    'Not sure',
    'N/A'
  ]);
}

function addSectionD_(form) {
  addPage_(form, 'Section D. Workforce and Clinic Operations');

  addMultipleChoice_(form, '16. How difficult is it for your clinic to recruit and retain qualified staff?', [
    'Not difficult',
    'Slightly difficult',
    'Moderately difficult',
    'Very difficult',
    'Extremely difficult',
    'Not sure',
    'N/A'
  ]);

  addCheckboxes_(form, '17. Which roles are hardest to recruit or retain? Check all that apply.', [
    'Physicians',
    'Nurse practitioners',
    'Physician assistants',
    'Certified nurse midwives',
    'Nurses',
    'Medical assistants',
    'Behavioral health providers',
    'Billing/coding staff',
    'Front desk/scheduling staff',
    'IT/data staff',
    'Care coordinators/patient navigators',
    'Other',
    'Not sure',
    'N/A'
  ]);

  addCheckboxes_(form, '18. Which operational tasks consume the most staff time? Choose up to five.', [
    'Prior authorizations',
    'Billing and claims follow-up',
    'Documentation',
    'Compliance reporting',
    'Quality reporting',
    'Referral tracking',
    'Patient follow-up',
    'Scheduling',
    'Manual spreadsheet tracking',
    'Data entry between systems',
    'Grant reporting',
    'Patient calls/messages',
    'Staff training or onboarding',
    'Other',
    'Not sure',
    'N/A'
  ], 'Select up to five.', 5);

  addMultipleChoice_(form, '19. Are there workflows that currently depend on manual spreadsheets, paper forms, or repeated copy-paste between systems?', [
    'Yes',
    'No',
    'Not sure',
    'N/A'
  ]);

  addParagraph_(form, '19a. If yes, please describe the manual workflows.');
  addParagraph_(form, '20. Where would workflow automation help the most?');
}

function addSectionE_(form) {
  addPage_(form, 'Section E. Clinical Care, Quality, and Continuity');

  addMultipleChoice_(form, '21. How well can your clinic identify patients who are overdue for preventive screenings, immunizations, or chronic disease follow-up?', [
    'Very well',
    'Somewhat well',
    'Not very well',
    'Not at all',
    'Not sure',
    'N/A'
  ]);

  addCheckboxes_(form, '22. Which care gaps are hardest to track or close? Check all that apply.', [
    'Diabetes A1c testing/control',
    'Hypertension follow-up/control',
    'Cancer screenings',
    'Immunizations',
    'Annual wellness visits',
    'Behavioral health follow-up',
    'Medication adherence',
    'Post-hospitalization follow-up',
    'ED utilization',
    'Maternal/child health follow-up',
    'Patient education follow-up',
    'Other',
    'Not sure',
    'N/A'
  ]);

  addMultipleChoice_(form, '23. How effective is your current referral tracking process?', [
    'Very effective',
    'Somewhat effective',
    'Inconsistent',
    'Mostly manual or unreliable',
    'We do not have a formal referral tracking process',
    'Not sure',
    'N/A'
  ]);

  addCheckboxes_(form, '24. What are the biggest barriers to care coordination? Check all that apply.', [
    'Limited staff time',
    'Difficulty obtaining specialist appointments',
    'Poor communication with hospitals/specialists',
    'No shared data system',
    'Transportation barriers',
    'Patient nonresponse',
    'Insurance barriers',
    'Lack of care coordinators or navigators',
    'Other',
    'Not sure',
    'N/A'
  ]);

  addParagraph_(form, '25. What patient safety or quality issues would you most like to improve?');
}

function addSectionF_(form) {
  addPage_(form, 'Section F. Revenue Cycle, Billing, and Financial Sustainability');

  addMultipleChoice_(form, '26. How would you rate your clinic\'s current financial sustainability?', [
    'Strong',
    'Stable but vulnerable',
    'Somewhat strained',
    'Highly strained',
    'Not sure',
    'N/A'
  ]);

  addCheckboxes_(form, '27. Which revenue-cycle challenges affect your clinic? Check all that apply.', [
    'Claim denials',
    'Coding errors',
    'Documentation gaps',
    'Delayed reimbursement',
    'Payer-contracting issues',
    'Medicare/RHC billing complexity',
    'Medicaid billing complexity',
    'Patient collections',
    'Cost reporting',
    'Underuse of reimbursable services',
    'Limited billing staff capacity',
    'Other',
    'Not sure',
    'N/A'
  ]);

  addMultipleChoice_(form, '28. Do you currently track denial rate, days in accounts receivable, clean claim rate, and reimbursement by payer?', [
    'Yes, routinely',
    'Yes, but manually or inconsistently',
    'No',
    'Not sure',
    'N/A'
  ]);

  addParagraph_(form, '29. Where do you believe the clinic is losing the most revenue or staff time?');

  addMultipleChoice_(form, '30. Would your clinic be interested in support that identifies billing errors, missed reimbursements, denial patterns, or documentation gaps?', [
    'Yes, high interest',
    'Maybe, depending on cost/workflow',
    'No',
    'Not sure',
    'N/A'
  ]);
}

function addSectionG_(form) {
  addPage_(form, 'Section G. Compliance, Reporting, and Risk');

  addCheckboxes_(form, '31. Which compliance areas are most challenging for your clinic? Check all that apply.', [
    'CMS/RHC certification requirements',
    'HIPAA/privacy/security',
    'State licensing requirements',
    'Emergency preparedness',
    'Clinical documentation',
    'Patient health records',
    'Quality assurance/performance improvement',
    'HRSA or grant-related reporting',
    'OSHA/workplace safety',
    'Staff credentialing/licensure tracking',
    'Other',
    'Not sure',
    'N/A'
  ]);

  addMultipleChoice_(form, '32. How confident are you that your clinic could quickly produce documentation for an audit, survey, or compliance review?', [
    'Very confident',
    'Somewhat confident',
    'Not very confident',
    'Not confident',
    'Not sure',
    'N/A'
  ]);

  addParagraph_(form, '33. What compliance tasks are currently most manual or burdensome?');

  addMultipleChoice_(form, '34. Would your clinic value a compliance dashboard or alert system that tracks requirements, deadlines, documentation gaps, and policy updates?', [
    'Yes, high value',
    'Some value',
    'Low value',
    'Not sure',
    'N/A'
  ]);
}

function addSectionH_(form) {
  addPage_(form, 'Section H. Data, Technology, and AI Readiness');

  addMultipleChoice_(form, '35. How often does leadership use data dashboards or reports to make operational decisions?', [
    'Weekly or more',
    'Monthly',
    'Quarterly',
    'Rarely',
    'We do not have dashboards/reports',
    'Not sure',
    'N/A'
  ]);

  addCheckboxes_(form, '36. What data sources are currently used for reporting or decision-making? Check all that apply.', [
    'EHR',
    'Practice management/billing system',
    'Claims data',
    'Spreadsheets',
    'Public health data',
    'HRSA/CMS reports',
    'Hospital or HIE data',
    'Patient surveys',
    'Manual staff knowledge',
    'Patient-worn device data',
    'Other',
    'Not sure',
    'N/A'
  ]);

  addCheckboxes_(form, '37. What data problems does your clinic experience? Check all that apply.', [
    'Data is hard to extract',
    'Data is spread across systems',
    'Reports take too long to build',
    'Data quality is inconsistent',
    'Staff lack time to analyze data',
    'Staff lack analytics training',
    'EHR reporting is limited',
    'We cannot easily benchmark performance',
    'We do not know which metrics to track',
    'Other',
    'Not sure',
    'N/A'
  ]);

  addMultipleChoice_(form, '38. How interested is your clinic in AI or analytics tools for rural health operations?', [
    'Very interested',
    'Somewhat interested',
    'Neutral',
    'Skeptical but open',
    'Not interested',
    'Not sure',
    'N/A'
  ]);

  addCheckboxes_(form, '39. Which AI or data use cases would be most valuable to your clinic? Choose up to five.', [
    'Compliance tracking',
    'Billing/denial analysis',
    'Preventive care gap identification',
    'Chronic disease risk stratification',
    'Social needs identification and referral tracking',
    'Staffing/capacity forecasting',
    'Grant opportunity tracking',
    'Public health/outbreak monitoring',
    'Automated reporting dashboards',
    'Patient communication support',
    'Referral leakage or follow-up tracking',
    'Patient-worn device data monitoring or integration',
    'Diagnostic AI tools or clinical decision-support tools',
    'AI-assisted patient documentation or record creation, with clinician review',
    'Other',
    'N/A / Not sure'
  ], 'Select up to five.', 5);

  addCheckboxes_(form, '40. What would prevent your clinic from adopting a new technology solution? Check all that apply.', [
    'Cost',
    'Staff time',
    'EHR integration concerns',
    'Privacy/security concerns',
    'Lack of IT support',
    'Staff resistance/change fatigue',
    'Unclear return on investment',
    'Too many existing systems',
    'Vendor trust concerns',
    'Other',
    'Not sure',
    'N/A'
  ]);

  addCheckboxes_(form, '41. What would make a new tool easier to adopt? Check all that apply.', [
    'Low cost',
    'Minimal setup',
    'Works with current EHR',
    'Clear ROI',
    'Staff training included',
    'Simple dashboard',
    'Compliance/HIPAA clarity',
    'Vendor provides ongoing support',
    'Pilot option before full commitment',
    'Technology training included',
    'Other',
    'Not sure',
    'N/A'
  ]);
}

function addSectionI_(form) {
  addPage_(form, 'Section I. Social Needs, Referrals, and Community Partnerships');

  addMultipleChoice_(form, '42. Does your clinic currently screen patients for social needs such as food, housing, transportation, utilities, or safety?', [
    'Yes, routinely',
    'Sometimes',
    'Rarely',
    'No',
    'Not sure',
    'N/A'
  ]);

  addCheckboxes_(form, '43. If your clinic screens for social needs, how is that information used? Check all that apply.', [
    'Documented in the EHR or patient record',
    'Used to refer patients to community resources',
    'Used by care coordinators, navigators, or social workers',
    'Used for quality improvement or population-health planning',
    'Used for grant reporting or funder reporting',
    'Used to identify high-risk patients',
    'Reviewed by leadership or care teams',
    'Collected but not consistently used',
    'We do not currently screen for social needs',
    'Other',
    'Not sure',
    'N/A'
  ]);

  addCheckboxes_(form, '44. If your clinic screens for social needs, how is that information documented?', [
    'Structured EHR fields',
    'Notes/free text',
    'Paper forms',
    'Spreadsheet',
    'Referral platform',
    'Not documented consistently',
    'We do not currently screen for social needs',
    'Other',
    'Not sure',
    'N/A'
  ]);

  addCheckboxes_(form, '45. Which social needs are most common among your patients? Choose up to five.', [
    'Transportation',
    'Food insecurity',
    'Housing instability',
    'Utility needs',
    'Medication affordability',
    'Health insurance coverage',
    'Behavioral health',
    'Substance use',
    'Social isolation',
    'Disability support',
    'Domestic violence/interpersonal safety',
    'Employment or income instability',
    'Other',
    'Not sure',
    'N/A'
  ], 'Select up to five.', 5);

  addCheckboxes_(form, '46. How do you currently connect patients to community resources?', [
    'Printed resource list',
    'Staff referral by phone/email',
    '211 or similar community resource directory',
    'Findhelp/Aunt Bertha or another referral platform',
    'Direct partnership with community organizations',
    'Warm handoff to navigator/social worker',
    'We do not have a consistent process',
    'Other',
    'Not sure',
    'N/A'
  ]);

  addCheckboxes_(form, '47. What makes social-needs referral difficult? Check all that apply.', [
    'Limited community resources',
    'Staff do not know where to refer',
    'No referral tracking system',
    'Patients cannot be reached after referral',
    'Transportation barriers',
    'Privacy/information-sharing concerns',
    'Lack of community partners',
    'Limited staff time',
    'Other',
    'Not sure',
    'N/A'
  ]);
}

function addSectionJ_(form) {
  addPage_(form, 'Section J. Emergency Preparedness and Public Health');

  addMultipleChoice_(form, '48. How prepared is your clinic to respond to public health emergencies, outbreaks, weather events, or sudden service disruptions?', [
    'Very prepared',
    'Somewhat prepared',
    'Not very prepared',
    'Not prepared',
    'Not sure',
    'N/A'
  ]);

  addCheckboxes_(form, '49. Which preparedness areas need improvement? Check all that apply.', [
    'Emergency communication plan',
    'Staffing contingency plan',
    'Supply chain/medication access',
    'Telehealth continuity',
    'Patient outreach during emergencies',
    'Coordination with local health department',
    'Infectious disease surveillance/reporting',
    'Backup data access',
    'Cybersecurity incident response',
    'Other',
    'Not sure',
    'N/A'
  ]);

  addMultipleChoice_(form, '50. Would real-time public health data, outbreak alerts, or service-area dashboards be useful to your clinic?', [
    'Very useful',
    'Somewhat useful',
    'Not useful',
    'Not sure',
    'N/A'
  ]);
}

function addSectionK_(form) {
  addPage_(form, 'Section K. Desired Support and Product Fit');

  addCheckboxes_(form, '51. Which types of support would be most valuable to your clinic? Choose up to seven.', [
    'Compliance readiness assessment',
    'Billing/revenue-cycle analysis',
    'Denial and coding error review',
    'Quality reporting dashboard',
    'Preventive care gap dashboard',
    'Chronic disease management analytics',
    'Social needs screening/referral workflow',
    'Care coordination and referral tracking',
    'Staff training',
    'Patient education resources',
    'Technology training',
    'Grant-writing or funding support',
    'Policy/procedure templates',
    'EHR/reporting optimization',
    'Cybersecurity/privacy assessment',
    'Emergency preparedness planning',
    'Public health data dashboard',
    'Diagnostic AI or clinical decision-support tools',
    'Patient documentation support tools',
    'Patient-worn device data integration',
    'Other',
    'Not sure',
    'N/A'
  ], 'Select up to seven.', 7);

  addCheckboxes_(form, '52. If a solution could save your clinic time or money, where would that impact matter most?', [
    'Fewer billing errors',
    'Faster reimbursement',
    'Less compliance burden',
    'Better patient follow-up',
    'Fewer missed care gaps',
    'Reduced staff burnout',
    'Better reporting for leadership/board/funders',
    'More grant funding',
    'Improved patient access',
    'Better patient education',
    'Other',
    'Not sure',
    'N/A'
  ]);

  addMultipleChoice_(form, '53. How soon would your clinic consider implementing a solution if it addressed your top needs?', [
    'Immediately',
    'Within 3 months',
    'Within 6 months',
    'Within 12 months',
    'Not currently considering new solutions',
    'Not sure',
    'N/A'
  ]);

  addCheckboxes_(form, '54. Who would need to be involved in deciding whether to adopt a new solution? Check all that apply.', [
    'Owner/CEO/Executive Director',
    'Medical Director',
    'Clinic Administrator',
    'Billing/Finance Lead',
    'IT/EHR Lead',
    'Compliance Officer',
    'Hospital/system leadership',
    'Board',
    'Other',
    'Not sure',
    'N/A'
  ]);

  addMultipleChoice_(form, '55. Would you be open to a short follow-up interview to discuss your clinic\'s needs in more detail?', [
    'Yes',
    'Maybe',
    'No',
    'Not sure',
    'N/A'
  ]);

  addParagraph_(form, '56. What else should we understand about your clinic\'s needs, barriers, or priorities?');
}

/* ----------------------------- Helper functions ----------------------------- */

function addSectionHeader_(form, title, helpText) {
  const item = form.addSectionHeaderItem().setTitle(title);
  if (helpText) item.setHelpText(helpText);
  return item;
}

function addPage_(form, title, helpText) {
  const page = form.addPageBreakItem().setTitle(title);
  if (helpText) page.setHelpText(helpText);
  return page;
}

function addText_(form, title, helpText) {
  const item = form.addTextItem().setTitle(title).setRequired(false);
  if (helpText) item.setHelpText(helpText);
  return item;
}

function addParagraph_(form, title, helpText) {
  const item = form.addParagraphTextItem().setTitle(title).setRequired(false);
  if (helpText) item.setHelpText(helpText);
  return item;
}

function addMultipleChoice_(form, title, options, helpText) {
  const item = form.addMultipleChoiceItem().setTitle(title).setRequired(false);
  if (helpText) item.setHelpText(helpText);

  const values = [];
  let hasOther = false;

  options.forEach(function(option) {
    if (isOtherOption_(option)) {
      hasOther = true;
    } else {
      values.push(option);
    }
  });

  item.setChoiceValues(values);
  if (hasOther) item.showOtherOption(true);

  return item;
}

function addCheckboxes_(form, title, options, helpText, maxSelections) {
  const item = form.addCheckboxItem().setTitle(title).setRequired(false);
  if (helpText) item.setHelpText(helpText);

  const values = [];
  let hasOther = false;

  options.forEach(function(option) {
    if (isOtherOption_(option)) {
      hasOther = true;
    } else {
      values.push(option);
    }
  });

  item.setChoiceValues(values);
  if (hasOther) item.showOtherOption(true);

  if (maxSelections) {
    const validation = FormApp.createCheckboxValidation()
      .requireSelectAtMost(maxSelections)
      .setHelpText('Please select no more than ' + maxSelections + ' option(s).')
      .build();

    item.setValidation(validation);
  }

  return item;
}

function isOtherOption_(option) {
  const normalized = String(option).trim().toLowerCase();
  return normalized === 'other' || normalized.indexOf('other:') === 0;
}
