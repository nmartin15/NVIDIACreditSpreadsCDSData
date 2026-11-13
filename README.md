# AI Credit Watch

Single-screen dashboard that tracks whether the credit market is repricing NVIDIA and the AI financing chain around it, using free public data.

## Run

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Fill the three values in `.env` using the steps below, then:

```
streamlit run app.py
```

`.env` is listed in `.gitignore`. Leave the keys only in that local file.

Check the credentials after they are filled in:

```
python scripts/probe_sources.py
```

FRED should print observations for `DGS10` and `BAMLC0A0CM`. FINRA should receive a token and list `fixedIncomeMarket` datasets. Treasury and DTCC run with no keys.

## API credentials

Two credentials are required. TreasuryDirect, Treasury Fiscal Data, DTCC public credit files, and Yahoo prices (via `yfinance`) need no account.

| Variable | Source | Cost |
| --- | --- | --- |
| `FRED_API_KEY` | St. Louis Fed, FRED | Free |
| `FINRA_CLIENT_ID` | FINRA API Platform, Public credential | Free |
| `FINRA_CLIENT_SECRET` | Same FINRA credential | Free |

This project does not call a paid CDS vendor (ICE, Markit, or S&P). No third key exists for that.

### FRED

The site is [fred.stlouisfed.org](https://fred.stlouisfed.org/). The key page is [fredaccount.stlouisfed.org/apikeys](https://fredaccount.stlouisfed.org/apikeys). Official notes: [API keys](https://fred.stlouisfed.org/docs/api/api_key.html) and [register](https://fred.stlouisfed.org/help/account/fred-account-features/register/).

1. Open [https://fred.stlouisfed.org/](https://fred.stlouisfed.org/).
2. Top right, click **My Account**.
3. Click **Create New Account**. **Register with Google** works too when that button is shown.
4. Use an email you can read today and a password you choose. Click **Create Account**. The account is active immediately.
5. Stay signed in and open [https://fredaccount.stlouisfed.org/apikeys](https://fredaccount.stlouisfed.org/apikeys). If it sends you to login, sign in and open that URL again. The same page is **My Account**, then **API Keys**.
6. Click **Request API Key**.
7. Description: `AI Credit Watch local dashboard`.
8. Accept the FRED API terms and click **Request API Key**.
9. Copy the key from that page. It is 32 lowercase letters and digits, with no spaces.
10. Paste it into `.env` as `FRED_API_KEY=...`.

One key is enough for this app. FRED asks for a distinct key per application.

Browser check (the key is in the URL, so do not share the tab):

`https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&api_key=YOUR_KEY&file_type=json&limit=1`

A working key returns JSON with an `observations` array.

The series this app requests include `DGS10` (10-year Treasury yield) and `BAMLC0A0CM` (ICE BofA US Corporate Index option-adjusted spread).

### FINRA

Start at [developer.finra.org](https://developer.finra.org/). Individual signup is described under [Getting Started](https://developer.finra.org/node/1146). Fees are on [Fees](https://developer.finra.org/fees). Fixed-income terms are on [Specific Terms for Fixed Income Data](https://developer.finra.org/specific-terms-fixed-income-data).

Create a **Public** credential. On the individual fee table that type is **$0 per month**, with a **10 GB per month** download cap. After the cap, FINRA turns that credential off until the next calendar month. A Firm credential is $1,650 per month. On the create form, the fee line should read $0. Public is the type this dashboard uses. Mock returns sample rows for dataset names ending in `Mock`, which will not feed the dashboard.

You will have two different secrets:

- **Gateway login password.** This signs you into the website. It expires every 120 days. The first password-reset link in email expires in **1 hour**. It does not go in `.env`.
- **API Client Secret.** This is the machine password. You choose it. The email link to set it expires in **24 hours**. The secret itself expires in **1 year**. FINRA emails about 30 days and 7 days before that. This value is `FINRA_CLIENT_SECRET`.

Use an inbox you can watch for the next hour, and check spam. One email address can hold only one Individual account.

#### Create the website account

1. Open [https://developer.finra.org/](https://developer.finra.org/).
2. In the top navigation, click **Console**. That opens the FINRA Gateway login page.
3. Click **Create Account Here**. The firm path (Super Account Administrator and an API Console Entitlement Request) is for firm-private data. This project uses the individual Public credential.
4. Submit the individual form with your name and email.
5. Open the FINRA email. It has the website user id and a password-reset link. If it is missing after a few minutes, check Junk. If nothing arrives within an hour, call the FINRA Support Center at **(301) 869-6699** and ask them to resend the individual API user password link. The link dies in one hour, and FINRA does not offer a self-serve second link.
6. Open the link, set a website password, and store it in a password manager as `FINRA Gateway login`.
7. You should land in the **API Console**. If you land on a generic Gateway home, open **</> API Console** in the left navigation. Later visits: [developer.finra.org](https://developer.finra.org/), **Console**, then this website user id and password.

#### Create the Public credential

1. Open **My Credentials**.
2. Click **ADD API CREDENTIAL** (the label may be **Add API Credential**).
3. Name: `AI Credit Watch`. That name is a label on the website. It does not go in `.env`.
4. Type: **Public**. Confirm the fee line says **$0**.
5. Accept the FINRA API Terms of Service and click **CREATE**.
6. Copy the **API Client user** value from the new row. FINRA also calls that string the API Client ID. That value is `FINRA_CLIENT_ID`. The page does not show a secret.
7. Two emails follow. Opening [developer.finra.org](https://developer.finra.org/) does not set the secret, and the **Important Information** email only repeats the client id.
   - **FINRA API Developer Center – Action Required**, with **Create API Client Secret**. The link expires in 24 hours. That link opens a Reset Password page. The password you type there is the API secret.
   - **FINRA API Developer Center – Important Information**, which repeats the API Client ID.
8. Open **Create API Client Secret** from the Action Required email. Check Junk if that email is missing. If the credential row is not active, use **Reset** on that row to send a new Action Required email.
9. In **User ID**, paste the **API Client user** value from the My Credentials row, or from the Important Information email. Personal Profile stays on the same login, and its User ID is not accepted here. FINRA responds: "The User ID entered does not match the User ID required for this Password Reset link or the link has expired." Use the client id from the newest Action Required email. If the link is old, click **Reset** on that credential and use the new email.
10. Choose a long password and type it twice. That password is `FINRA_CLIENT_SECRET`. Save it before you click Save. FINRA does not show it again.
11. Click **SAVE**. My Credentials should show the credential as active. If the 24-hour link already expired, sign into the API Console, click **Reset** on that credential, and use the new email the same way.

`.env` then looks like:

```
FRED_API_KEY=your 32-character fred key
FINRA_CLIENT_ID=the client id from My Credentials
FINRA_CLIENT_SECRET=the password you typed on the Reset Password page
```

The app trades that pair for a short-lived access token. A bearer token does not belong in `.env`. FINRA's token URL is `https://ews.fip.finra.org/fip/rest/ews/oauth2/access_token` with grant type `client_credentials`.

If a screen or email fails: **api_developer@finra.org**, or **(301) 869-6699**.

### Sources with no signup

- TreasuryDirect auction service: [treasurydirect.gov/TA_WS/securities/auctioned](https://www.treasurydirect.gov/TA_WS/securities/auctioned) and `/securities/search`.
- Treasury Fiscal Data: [API documentation](https://fiscaldata.treasury.gov/api-documentation/). Treasury states this API does not require an account or a token. Auction fallback used here: `https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/od/auctions_query`.
- DTCC public credit files: `https://pddata.dtcc.com/ppd/api/general/bucketname`, then a public JSON file.
- Yahoo Finance equity prices through `yfinance`.
