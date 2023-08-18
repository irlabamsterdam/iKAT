<h1>TREC Interactive Knowledge Assistance Track (iKAT)</h1>

The iKAT builds on the experience of four successful years of the TREC Conversational Assistance Track (CAsT), 
where the key focus of iKAT is on researching and developing collaborative information seeking conversational agents 
which can tailor and personalize their response based on what they learn about and from the user.

The fourth year of CAsT aimed to add more conversational elements to the interaction streams, by introducing mixed initiatives 
(clarifications, and suggestions) to create multi-path, multi-turn conversations for each topic. 
TREC iKAT evolves CAsT into a new track to signal this new trajectory. 
The iKAT aims to focus on supporting multi-path, multi-turn, multi-perspective conversations, i.e., for a given topic, the direction and the conversation that evolves depends not only on the prior responses but also on the user (and their background/perspective/context/etc). As different personas undertake various topics, systems need to build and develop a picture of who the user is, in order to best address their information needs. Put another way, iKAT focuses on a system understanding of user knowledge and information needs in accordance with the available context.

This is the first year of iKAT which will run as a task in TREC. This year we focus on generating personalized responses. 
The personal information of the user is provided in the Personalized Text Knowledge Base (PTKB) which is a set of natural language sentences. 
The PTKB of the user is provided at the beginning of the conversation to the system. 
To generate a personalized response, the system should undertake the following main steps:

<ul>
  <li>Read the current dialogue turns up to the given turn (context): The provided context is: (1) A fixed set of previous responses with provenance in the preceding turns up to the current step, and (2) PTKB of the user. (Note: Using information from following turns is not allowed.)</li>
  <li>Find the relevant statements from PTKB to the information needed for this turn: This task is considered a relevance score prediction. The output is in the form of a sorted list of statements from PTKB with corresponding relevance scores.</li>
  <li>Extract or generate a response: Each response can be generated from multiple passages. It can be an abstractive or extractive summary of the corresponding passages. Each response must have one or more ranked passages as provenance used to produce it.</li>
</ul>

The relevant PTKB statements from the second step would be used in the next step. 

<h1>Year 1 (iKAT 2023)</h1>
<h2>Data</h2>

<h3>Topics</h3>

The test and train topics can be found <a href="https://github.com/irlabamsterdam/iKAT/tree/main/2023/data">here</a>.

<h3>Collection</h3>

The collection is a subset of the ClueWeb22 dataset. The collection distribution is being handled directly by CMU and not the iKAT organizers. Please follow these steps to get your data license ASAP:

<br>
<ul>
  <li>Sign the license form available on the ClueWeb22 project web page.</li>
  <li>Send the form to CMU for approval (jlm4@andrew.cmu.edu)</li>
</ul>

Please give enough time to the CMU licensing office to accept your request. A download link will be sent to you by the ClueWeb22 team at CMU.
<br>

Note:

<ul>
  <li>CMU requires a signature from the organization (i.e., the university or company), not an individual who wants to use the data. This can slow down the process at your end too. So, it’s useful to start the process ASAP.</li>
  <li>If you already have an accepted license for ClueWeb22, you don’t need a new form. Please let us know if that’s the case.</li>
</ul>

<h3>Baslines</h3>

Will be added soon.

<h2>Guidelines</h2>

The guideline for participants of iKAT can be found <a href="https://docs.google.com/document/d/1dso0VANm5Q08UWt4ppZvzvH6zkpRhfoukwpBgeJNbHE/edit#heading=h.wtcnmcfjg1h">here</a>.

<h2>Contact</h2>
<ul>
  <li>Twitter: @trec_ikat</li>
  <li>Email: trec.ikat.ai@gmail.com</li>
  <li>Google Groups: trec-ikat@googlegroups.com</li>
  <li>Slack: ikat-2023</li>
</ul>

<h2>Organizers</h2>
<ul>
  <li>Mohammad Aliannejadi, University of Amsterdam</li>
  <li>Zahra Abbasiantaeb, University of Amsterdam</li>
  <li>Shubham Chatterjee, University of Glasgow</li>
  <li>Jeff Dalton, University of Glasgow</li>
  <li>Leif Azzopardi, University of Strathclyde</li>
</ul>






