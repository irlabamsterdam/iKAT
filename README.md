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
The PTKB of the user is provided at the beging of the conversation to the system. 
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
<h3>Corpora</h3>
<h3>Baslines</h3>

<h2>Guidelines</h2>
<h2>Contact</h2>
<h2>Organizers</h2>
