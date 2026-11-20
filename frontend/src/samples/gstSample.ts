import GST_RULES_TEXT from './ShreshtiAI_Sample_GST_Invoice_Rules.txt?raw';
import { uploadGuideline } from '../services/api';
import { GuidelineUploadResponse } from '../types/api';

/** File name the sample GST rules are stored under; also used to find them in the scope list. */
export const GST_RULES_FILENAME = 'ShreshtiAI_Sample_GST_Invoice_Rules.txt';

/** A regular taxpayer's invoice with a mix of compliant, non-compliant and unclear lines. */
export const SAMPLE_INVOICE_TEXT =
  'We charge IGST at 18% on this intra-state supply from Birur to Davanagere. ' +
  'The tax invoice shows the GSTIN of the supplier. ' +
  'The tax invoice shows the date of issue. ' +
  'We claim input tax credit on goods used for personal consumption. ' +
  'Payment is due 90 days from the day of acceptance.';

/** Events the guided tour and the demo buttons use to drive the page. */
export const DEMO_EVENTS = {
  loadGst: 'shreshti:load-gst',
  gstLoaded: 'shreshti:gst-loaded',
  fillInvoice: 'shreshti:fill-invoice',
  runCheck: 'shreshti:run-check',
  reviewDone: 'shreshti:review-done',
  startTour: 'shreshti:start-tour',
} as const;

export const isGstRulesFile = (filename: string | null | undefined): boolean =>
  !!filename && filename.toLowerCase().startsWith('shreshtiai_sample_gst');

/** Uploads the bundled GST rules. The backend reuses the record if the same file is already indexed. */
export async function loadGstRules(): Promise<GuidelineUploadResponse> {
  const file = new File([GST_RULES_TEXT], GST_RULES_FILENAME, { type: 'text/plain' });
  return uploadGuideline(file);
}
