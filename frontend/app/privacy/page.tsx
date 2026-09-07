// Privacy policy page.

import type { Metadata } from "next";
import Link from "next/link";
import { LegalShell } from "@/components/legal-shell";
import { LegalSection } from "@/components/legal-section";

export const metadata: Metadata = {
  title: "Privacy Policy — MeetMind",
  description:
    "How MeetMind collects, uses, and protects your data — including how meetings, transcripts, and summaries are handled.",
};

const LAST_UPDATED = "September 7, 2026";

const bulletLinkClassName =
  "font-medium text-primary underline-offset-4 hover:underline";

export default function PrivacyPage() {
  return (
    <LegalShell title="Privacy Policy" lastUpdated={LAST_UPDATED}>
      <LegalSection id="information-we-collect" title="Information We Collect">
        <p>
          When you use MeetMind, we collect the following categories of
          information:
        </p>
        <ul className="list-disc space-y-2 pl-5">
          <li>
            <span className="font-medium text-foreground">
              Account information
            </span>{" "}
            — your name and email address. If you sign in with Google, we
            receive your Google profile information (such as your name and
            email) to create and link your account.
          </li>
          <li>
            <span className="font-medium text-foreground">Meeting content</span>{" "}
            — the audio and video files you upload, along with the transcripts
            and AI-generated summaries we create from them.
          </li>
          <li>
            <span className="font-medium text-foreground">
              Usage and session data
            </span>{" "}
            — including an authentication cookie that keeps you signed in and
            refreshes your session.
          </li>
        </ul>
      </LegalSection>

      <LegalSection
        id="how-we-use-your-information"
        title="How We Use Your Information"
      >
        <p>
          We use the information we collect to provide and improve the service,
          specifically to:
        </p>
        <ul className="list-disc space-y-2 pl-5">
          <li>Transcribe your audio and video recordings.</li>
          <li>Generate summaries and action items from those recordings.</li>
          <li>
            Power the chat feature, which lets you ask questions about your
            meetings using retrieval across your recordings.
          </li>
          <li>Authenticate you and keep your session secure.</li>
          <li>Improve the product based on how it is used.</li>
        </ul>
      </LegalSection>

      <LegalSection id="third-party-services" title="Third-Party Services">
        <p>
          To provide the service, we work with a small number of processors:
        </p>
        <ul className="list-disc space-y-2 pl-5">
          <li>
            <span className="font-medium text-foreground">
              Cloud storage provider
            </span>{" "}
            — your uploaded audio and video files are stored by a cloud storage
            provider (such as Amazon S3).
          </li>
          <li>
            <span className="font-medium text-foreground">
              AI service provider
            </span>{" "}
            — transcription, summarization, and chat are powered by an AI
            service provider. Portions of your meeting content may be processed
            by this provider to generate transcripts, summaries, and answers.
          </li>
          <li>
            <span className="font-medium text-foreground">Google</span> — if
            you choose to sign in with Google OAuth, Google provides your
            identity information to us.
          </li>
        </ul>
        <p>
          We do not sell your personal information or your meeting content to
          third parties.
        </p>
      </LegalSection>

      <LegalSection
        id="data-retention-and-deletion"
        title="Data Retention and Deletion"
      >
        <p>
          You can delete individual meetings at any time from within the app.
          Deleting a meeting removes the uploaded recording and the associated
          transcript and summary data. We do not retain these records beyond
          what is needed to operate the service.
        </p>
        <p>
          If you would like to delete your account and the data associated with
          it, please contact us through our{" "}
          <Link href="/contact" className={bulletLinkClassName}>
            Contact page
          </Link>{" "}
          and we will assist you.
        </p>
      </LegalSection>

      <LegalSection id="cookies" title="Cookies">
        <p>
          MeetMind uses a single, secure (HTTP-only) authentication cookie to
          keep you signed in and to refresh your session when it expires. We do
          not use cookies for advertising or cross-site tracking.
        </p>
      </LegalSection>

      <LegalSection id="your-rights" title="Your Rights">
        <p>
          You have the right to delete your own meetings and associated data,
          and to request deletion of your account. You may also contact us at
          any time with questions about how your data is handled. To exercise
          any of these rights, use the{" "}
          <Link href="/contact" className={bulletLinkClassName}>
            Contact page
          </Link>
          .
        </p>
      </LegalSection>

      <LegalSection id="data-security" title="Data Security">
        <p>
          We take reasonable measures to protect your data, including encrypting
          data in transit and restricting access to your information to
          authorized systems. No method of transmission or storage is completely
          secure, and we cannot guarantee absolute security.
        </p>
      </LegalSection>

      <LegalSection id="no-sale-of-data" title="No Sale of Data">
        <p>
          We do not sell your personal information or your meeting content. Your
          data is used solely to provide and improve the MeetMind service as
          described in this policy.
        </p>
      </LegalSection>

      <LegalSection id="changes-to-this-policy" title="Changes to This Policy">
        <p>
          We may update this Privacy Policy from time to time. When we do, we
          will revise the &ldquo;Last updated&rdquo; date at the top of this
          page. We encourage you to review this policy periodically.
        </p>
      </LegalSection>

      <LegalSection id="contact-us" title="Contact Us">
        <p>
          If you have questions about this Privacy Policy or about how your data
          is handled, please reach out through our{" "}
          <Link href="/contact" className={bulletLinkClassName}>
            Contact page
          </Link>
          .
        </p>
      </LegalSection>
    </LegalShell>
  );
}
