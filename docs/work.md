---
title: Work
nav_order: 2
has_children: true
has_toc: false
permalink: /work/
description: Selected analytics, AI and financial-services work from the Fintech Analytics AI project.
---

# Work

Four surfaces on one tested warehouse. Each case is a business problem, not a feature list. The source data is synthetic; the models, tests and guardrails are real.

<p class="case-tech">21 dbt models · 83 data-quality tests · 57 governed metrics · 3 semantic models</p>

<article class="case-index">
<p class="case-k">Financial analytics</p>
<h2>Semantic layer and metric trust</h2>
<p><span class="case-k">Problem</span> The same commercial figure is easy to define differently in a dashboard, a chat answer and a report.</p>
<p><span class="case-k">Approach</span> Compute each metric once in dbt, test the grain, and publish it through MetricFlow.</p>
<p><span class="case-k">Why it matters</span> Two consumers, two query paths, one definition — so dashboard and AI cannot drift.</p>
<p class="case-tech">dbt Core · MetricFlow · SQL · Postgres</p>
<p><a href="{{ '/03-semantic-layer-and-metric-trust.html' | relative_url }}">Read the case →</a></p>
</article>

<article class="case-index">
<p class="case-k">Decision support</p>
<h2>Executive dashboard</h2>
<p><span class="case-k">Problem</span> An executive needs a few comparisons that answer whether activity, revenue and funding are on plan — not every column.</p>
<p><span class="case-k">Approach</span> Shape serving marts for known queries. Choose KPIs that support a decision.</p>
<p><span class="case-k">Why it matters</span> The marts are fit for consumption, and things can be left off the screen.</p>
<p class="case-tech">Python · SQL · Streamlit</p>
<p><a href="{{ '/01-what-i-built.html' | relative_url }}#executive-dashboard">Read the case →</a></p>
</article>

<article class="case-index">
<p class="case-k">Governed AI</p>
<h2>BI Assistant</h2>
<p><span class="case-k">Problem</span> Ad-hoc questions are useful. Letting a model write SQL produces confident, plausible, wrong answers.</p>
<p><span class="case-k">Approach</span> Allowlisted metrics, MetricFlow execution, pandas for arithmetic, then an LLM that only sees returned numbers.</p>
<p><span class="case-k">Why it matters</span> Neither model invents a business number. Cheap questions stay cheap.</p>
<p class="case-tech">MetricFlow · Python · pandas</p>
<p><a href="{{ '/01-what-i-built.html' | relative_url }}#bi-assistant">Read the case →</a></p>
</article>

<article class="case-index">
<p class="case-k">Management reporting</p>
<h2>AI CFO report</h2>
<p><span class="case-k">Problem</span> Leadership still needs a structured view of what happened when nobody typed a question.</p>
<p><span class="case-k">Approach</span> A fixed nine-section report, generated on a schedule. Every quantitative element is computed in Python first.</p>
<p><span class="case-k">Why it matters</span> A report worth reading needs deterministic inputs and a template, not a one-shot prompt.</p>
<p class="case-tech">Airflow · Python · Jinja2</p>
<p><a href="{{ '/01-what-i-built.html' | relative_url }}#ai-cfo-report">Read the case →</a></p>
</article>
