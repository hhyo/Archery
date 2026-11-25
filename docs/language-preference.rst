Interface language preference
=============================

Use the language selector on the login page or in the navigation bar to choose
Simplified Chinese or English, then press Apply. The page reloads at its current
URL, including query parameters. Save any unfinished edits before switching.

The preference is stored in Django's language cookie for one year. It survives
login and logout in the same browser, but is not synchronized across devices.
Clearing browser cookies removes the preference. Without a saved choice, the
browser's supported language is used, falling back to Simplified Chinese.

English coverage includes login and two-factor prompts, navigation, SQL workflows,
queries, analysis and optimization, slow logs, instance/database/account/parameter
management, query access, exports, archival, tools, configuration, Django admin
forms and navigation, and OpenAPI summaries and validation messages. Table, date
picker and file-upload controls follow the selected language.

User-provided names, SQL, database identifiers, stored logs, external engine error
details and protocol values retain their original content. Translation coverage
can still vary for third-party tools and engine execution reports. Switching the
language reloads the page and does not preserve unfinished form edits.

Implementation
--------------

``LocaleMiddleware`` activates the request language. The CSRF-protected
``POST /i18n/setlang/`` endpoint accepts ``zh-hans`` and ``en`` and delegates
cookie persistence and safe redirects to Django's ``set_language`` view.
The dashboard fragment cache varies by language to prevent one language from
being reused for another request. Browser scripts load Django's JavaScript
translation catalog before shared UI helpers. No database migration is required.

The database-free regression tests are in ``common/test_language.py`` and can
run with the project's configured Django test environment::

    python manage.py test common.test_language

Validation
----------

The regression suite covers cookie persistence and safe redirects, CSRF,
request-language rendering, admin navigation and forms, JavaScript catalogs,
localized component settings, stable action values, and validation branches that
must not query engines, change permissions or queue tasks. It uses mocked
connections for engine, storage and authentication checks.

Local browser checks exercised Chinese/English switching, reload persistence,
read-only pages and safe invalid-input branches. Actual SQL execution, workflow
approvals, configuration saves, SMS/email sending and storage connections were
not used for translation validation.
