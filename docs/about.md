---
title: About this project
nav_order: 4
has_children: true
has_toc: false
permalink: /about/
description: What this project is, how to read it, and which skills it demonstrates.
---

# About this project

I work where analytics engineering meets financial analysis: take a commercial question, turn it into a tested data product, and put the result in a form someone can decide from.

This site is a portfolio project at that intersection — warehouse modelling, metric governance, BI, and AI that is only allowed to explain numbers the warehouse already computed. It is not a client engagement and not a production deployment.

The commercial logic is modelled on a retail trading broker. The source data is simulated, on purpose: an analytics engineer does not generate source systems. The work to judge is the transformation, the tests, the metric contract, and how those numbers are used.

The modelling layer is mine. The Streamlit surfaces and larger Python modules were built with an AI coding agent under my direction and review.

## How to read this

<div class="path-grid">
  <article class="path-card">
    <p class="work-entry__cat">Recruiters and hiring managers</p>
    <h3>Five-minute guide</h3>
    <p>Enough to place the profile, see what shipped, and know which skills are claimed.</p>
    <ol>
      <li><a href="{{ '/cv/' | relative_url }}">CV</a> — roles, education, certifications</li>
      <li><a href="{{ '/01-what-i-built.html' | relative_url }}">What I built</a> — four surfaces and the daily pipeline</li>
      <li><a href="{{ '/06-skills.html' | relative_url }}">Skills demonstrated on this project</a> — technical, business and soft skills, with evidence</li>
    </ol>
  </article>
  <article class="path-card">
    <p class="work-entry__cat">Heads of analytics, BI and data</p>
    <h3>Fifteen-minute guide</h3>
    <p>Enough to judge the warehouse, the metric contract, and how AI is constrained.</p>
    <ol>
      <li><a href="{{ '/02-architecture-and-data-model.html' | relative_url }}">Architecture and data model</a> — layers, grain, why each model exists</li>
      <li><a href="{{ '/03-semantic-layer-and-metric-trust.html' | relative_url }}">Semantic layer and metric trust</a> — the core of the work</li>
      <li><a href="{{ '/04-bi-implementation-strategy.html' | relative_url }}">BI implementation strategy</a> — putting AI in front of a warehouse</li>
      <li><a href="{{ '/05-ownership-and-cursor-workflow.html' | relative_url }}">How this project was built</a> — what I built, what an agent built, how I QA it</li>
    </ol>
  </article>
</div>

<p class="about-also">The <a href="{{ '/07-file-guide.html' | relative_url }}">file guide</a> lists which repository files are worth opening.</p>
