from pydantic import BaseModel

from api.schemas.chat import Feedback
from api.schemas.user import UserData

from . import llm


async def explain_suggestion(
    user: UserData,
    agent: str,
    objective: str,
    problem: str | None,
    context: str,
    message: str,
) -> Feedback:
    objective_prompts = {
        ("yes-no-question", True): """
{user} asked a yes-or-no question that could be interpreted as either a yes or no
question or as a request for more information. {agent} could respond with a yes or no
answer, which is not what {user} is looking for. Instead, {user} should ask a
direct question to get the information they wanted from {agent}. Explain the specific
phrasing of the question that could be misinterpreted as simply a yes or no question,
and explain that the correct interpretation is unclear. Briefly mention people have
different communication styles and some may prefer direct language to avoid confusion.
""",
        ("yes-no-question", False): """
{user} asked a clear and direct question, avoiding the use of a yes-or-no question
that could be misinterpreted. This phrasing is more likely to elicit the information
that {user} is looking for as it is clear what information is being requested. Briefly
mention people have different communication styles and some may prefer direct language
to avoid confusion.
""",
        (
            "non-literal-emoji",
            True,
        ): """
{user} used an emoji in a non-literal way that could be misinterpreted by {agent}.
Explain specifically how emoji could be interpreted literally,and how this could be
confusing and misinterpreted. Therefore, {user} should use an emoji that clearly conveys
the intended meaning of the message. Briefly mention people have different communication
styles and some may prefer straightforward or no use of emojis to avoid confusion.

""",
        ("non-literal-emoji", False): """
{user} used an emoji in a clear and direct way, adding a visual element to their
message that enhances the meaning in a way that does not cause confusion. Briefly
mention people have different communication styles and some may prefer straightforward
or no use of emojis to avoid confusion.
""",
        ("non-literal-figurative", True): """
{user} used figurative language that could be misinterpreted as literal. Explain
specifically how the figurative language could be interpreted literally by {agent}, and
how this could be confusing and misinterpreted. Therefore, {user} should use clear and
direct language to convey their message. Briefly mention people have different
communication styles and some may prefer straightforward language to avoid confusion.
""",
        ("non-literal-figurative", False): """
{user} used clear and direct language to convey their message, avoiding the use of
figurative language that could be misinterpreted. This direct language is more likely
to be understood as intended. Briefly mention people have different communication styles
and some may prefer straightforward language to avoid confusion.
""",
        ("blunt-misinterpret", True): """
{user} was confrontational in response to {agent}'s blunt and direct language and
misinterpreted {agent}'s blunt language as rude. Explain how this might be {agent}'s
natural way of speaking. Clarify to {user}
what {agent} probably wanted to convey and that they did not intend to be rude. Briefly
mention that {user} should consider resonding in a more neutral way since people may
have different communication styles, and some may naturally sound blunt.
""",
        ("blunt-misinterpret", False): """
{user} responded appropriately to {agent}'s blunt language, considering that their blunt
language was not intended to be rude. {user}'s message is clear and direct, and it is
not confrontational to blunt language. Briefly mention that {user} should consider
resonding in a more neutral way since people may have different communication styles,
and some may naturally sound blunt.
""",
        ("generic", False): """
You are provided with {user}'s response to {agent}. Explain how {agent} will likely
interpret {user}'s emotional tone and intent from their message.
""",
    }
    objective_prompt = objective_prompts[(objective, problem is not None)].format(
        user=user.name, agent=agent
    )

    action = (
        (
            """
Now, explain to {user} why their original message could be misinterpreted by {agent}.
The problem might possibly be that {problem}. Base your feedback on {agent}'s likely
thought process, their understanding of the tone and intent of {user}'s message, and
their likely response.

Here are some guidelines to help you provide feedback:
{objective_prompt}

Make sure to:

1. In your explanation, refer to specific phrase(s) using quotation marks from the original message that make it confusing.
2. Use simple, friendly, and straightforward language.
3. Limit your answer to less than 100 words.
4. Provide feedback, but NEVER provide alternative messages.

Secondly, provide a title with less than 50 characters that accurately summarizes your feedback alongside an emoji.

Remember, explain to {user} what elements of the original message might be confusing for {agent}.
You MUST NEVER repeat the original message in your feedback.


At the end is a model output based on the following sample original message:
"How about we find a place where we can dip our toes in the ocean right from our balcony?"

{{
    "title": "Clarify Figurative Expressions 🗣️",
    "feedback": "When you mention 'dip our toes in the ocean right from our balcony,' Stephanie could take it literally, thinking you actually want to be able to dip your toes in the ocean from the balcony. It might help to clearly specify that you're looking for a place with an ocean view and easy beach access to avoid confusion! 😊"
}}
"""
        )
        if problem is not None
        else (
            """
Now, explain to {user} why their original message is likely to be interpreted correctly by {agent}.
Base your feedback on {agent}'s likely thought process, their understanding of the tone and intent of {user}'s message, and their likely response.

Here are some guidelines to help you provide feedback:
{objective_prompt}

Make sure to:

1. In your explanation, refer to specific phrase(s) using quotation marks from the original message that make it clear.
2. Use simple, friendly, and straightforward language.
3. Limit your answer to less than 100 words.

Secondly, provide a title with less than 50 characters that accurately summarizes your feedback alongside an emoji.

Remember, explain to {user} what elements of the original message make it a clear message for {agent}.
You MUST NEVER repeat the original message in your feedback.


At the end is a model output based on the following sample original message:
"When would be a good time for you to plan a trip to Gloucester?"

{{
    "title": "Clear and Specific 🗓️",
    "feedback": "Your message seems clear and direct, asking for specific information regarding the timing of the trip. This will likely make it easier for Sean to understand exactly what information you are seeking and provide a useful and detailed response. There is no figurative language or ambiguity that could lead to confusion."
}}
"""
        )
    )

    action = action.format(
        user=user.name, agent=agent, problem=problem, objective_prompt=objective_prompt
    )

    system_prompt_template = """
As a helpful communication guide, you are guiding {user} on their conversation with {agent}.

Respond with a JSON object with keys "title" and "feedback" containing your feedback.
"""

    system = system_prompt_template.format(
        objective_prompt=objective_prompt,
        user=user.name,
        agent=agent,
    )

    prompt_template = """
Here is the conversation history between {user} and {agent}:
{context}

Here is the original message last sent by {user}:
{original}

{action}
"""

    prompt = prompt_template.format(
        user=user.name, agent=agent, context=context, original=message, action=action
    )

    out = await llm.generate(
        schema=FeedbackOutput,
        model=llm.Model.GPT_4o,
        system=system,
        prompt=prompt,
    )

    return Feedback(title=out.title, body=out.feedback)


class FeedbackOutput(BaseModel):
    title: str
    feedback: str


async def explain_message(
    user: UserData,
    agent: str,
    objective: str,
    problem: str,
    message: str,
    context: str,
    reaction: str,
    last3: str | None,
) -> Feedback:
    if not last3:
        last3 = "** Not given **"
    objective_prompts = {
        "yes-no-question": """
{user} asked a yes-or-no question that could be interpreted as either a yes or no
question or as a request for more information. {agent} responded with a yes or no
answer, which is not what {user} is looking for. Instead, {user} should have asked a
direct question to get the information they wanted from {agent}. Explain the specific
phrasing of the question that was misinterpreted as simply a yes or no question,
and explain that the correct interpretation is unclear. Briefly mention people have
different communication styles and some may prefer direct language to avoid confusion.
""",
        "non-literal-emoji": """
{user} used an emoji in a non-literal way that was misinterpreted by {agent}.
Explain specifically how emoji was interpreted literally, and how this was
confusing and misinterpreted. Therefore, {user} should have used an emoji that clearly
conveyed the intended meaning of the message. Briefly mention people have different
communication styles and some may prefer straightforward or no use of emojis to avoid
confusion.

""",
        "non-literal-figurative": """
{user} used figurative language that was misinterpreted as literal. Explain
specifically how the figurative language was interpreted literally by {agent}, and
how this was confusing and misinterpreted. Therefore, {user} should have used clear and
direct language to convey their message. Briefly mention people have different
communication styles and some may prefer straightforward language to avoid confusion.
""",
        "blunt-misinterpret": """
{user} was confrontational in response to {agent}'s blunt and direct language and
misinterpreted {agent}'s blunt language as rude. First, float the idea that {agent} was
possibly just being straightforward as this might be {agent}'s
preferred way of speaking; explain the meaning of their blunt message from this perspective.
This is the blunt message by {agent}:
{last3}

Then, briefly mention that {user} should consider
resonding in a more thoughtful way since people may have different communication styles,
and some may naturally sound blunt.
""",
    }

    examples = {
        "blunt-misinterpret": """
At the end is a model output to help you out:
Blunt message by John: Kyle, we already talked about finding budget-friendly places. How about you just search for some cheap hostels or Airbnbs? We don't have time to go back and forth on this.
Confrontational message by Kyle: I thought you would have some suggestions ready.
John's reaction: I didn't mean I wouldn't help, Kyle. I thought you'd want to find some options since you're so into exploring and all that. I can help you search if you need it.

{{
    "title": "Avoid Confrontational Tone 🗣️",
    "feedback": "John was possibly just being straightforward and wanted to clarify that you should look for cheap hostels or Airbnbs as there is not a lot of time left until the trip. The phrase 'I thought you would have some suggestions ready' can come across as confrontational and show annoyance. John might have taken this as you being upset that he didn't have recommendations prepared. This might not have been clear, likely causing the misunderstanding."
}}
""",
        "figurative": """
At the end is a model output based on the following sample original message:
"How about we find a place where we can dip our toes in the ocean right from our balcony?"

{{
    "title": "Clarify Figurative Expressions 🗣️",
    "feedback": "When you mentioned 'dip our toes in the ocean right from our balcony,' Stephanie took it literally, thinking you actually wanted to be able to dip your toes in the ocean from the balcony. It might have helped to clearly specify that you're looking for a place with an ocean view and easy beach access to avoid confusion! 😊"
}}
""",
    }

    example = examples.get(objective, examples["figurative"])

    objective_prompt = objective_prompts[objective].format(
        user=user.name, agent=agent, last3=last3
    )

    system_prompt_template = """
As a helpful communication guide, you are guiding {user} on their conversation with {agent}.

Respond with a JSON object with keys "title" and "feedback" containing your feedback.
"""

    system = system_prompt_template.format(
        objective_prompt=objective_prompt,
        user=user.name,
        agent=agent,
    )

    prompt_template = """
{objective_prompt}

Here is the conversation history between {user} and {agent}:
{context}

Here is the original message last sent by {user}:
{original}

Here is {agent}'s response to {user}'s message above:
{reaction}

Now, explain to {user} why their original message was misinterpreted by {agent}.
The problem might possibly be that {problem}. Base your feedback on {agent}'s likely thought process and response provided above.

Make sure to:

1. In your explanation, refer to specific phrase(s) using quotation marks from the original message that make it confusing.
2. Use simple, friendly, and straightforward language.
3. Limit your answer to less than 100 words.
4. Provide feedback, but NEVER provide alternative messages.

Secondly, provide a title with less than 50 characters that accurately summarizes your feedback alongside an emoji.

Remember, explain to {user} what elements of the original message are confusing for {agent}.
You MUST NEVER repeat the original message in your feedback.

{example}
"""

    prompt = prompt_template.format(
        user=user.name,
        agent=agent,
        context=context,
        original=message,
        reaction=reaction,
        problem=problem,
        objective_prompt=objective_prompt,
        example=example,
    )

    out = await llm.generate(
        schema=FeedbackOutput,
        model=llm.Model.GPT_4o,
        system=system,
        prompt=prompt,
    )

    return Feedback(title=out.title, body=out.feedback)


class FeedbackContentOnly(BaseModel):
    feedback: str


async def explain_message_alternative(
    user: UserData,
    agent: str,
    objective: str,
    message: str,
    context: str,
    original: str,
    feedback_original: str,
) -> str:
    objective_prompts = {
        "yes-no-question": """
{user} asked a question that could be answered by either a simple yes or no statement or
as a request for more information.
""",
        "non-literal-emoji": """
{user} used an emoji in a non-literal way that was be misinterpreted. Explain
specifically how the emoji was interpreted literally by {agent}, and why this was
confusing. {user} should use an emoji that clearly conveys the intended meaning of their
message.
""",
        "non-literal-figurative": """
{user} used figurative language that was misinterpreted as literal. Explain specifically
how the figurative language was interpreted literally by {agent}, and how this could be
confusing. Instead, {user} should use clear and direct language to convey their message.
""",
        "blunt-misinterpret": """
{user} was confrontational in response to {agent}'s blunt and direct language, and
misinterpreted {agent}'s blunt language as rude. Explain how some individuals naturally
use blunt language and that {agent} did not intend to be rude. Instead, {user} should
consider that {agent} did not intend to be rude, and resond in a more understanding way.
""",
    }
    objective_prompt = objective_prompts[objective].format(user=user.name, agent=agent)

    system = f"""
As a helpful communication guide, you are guiding {user.name} on their conversation with {agent}.

{objective_prompt}

Respond with a JSON object with key "feedback" containing your feedback.
"""
    prompt = f"""
Here is the conversation history between {user.name} and {agent}:
{context}

Here is the original message last sent by {user.name}:
{original}

Here is the alternative message for the message above:
{message}

{user.name} received the following feedback on their original message:
{feedback_original}

Now, explain to {user.name} why the alternative message is better than their original message.

Make sure to:

1. Focus on the specific phrase(s) in the alternative that make it better.
2. Use simple, specific and straightforward language.
3. Limit your answer to less than 100 words.
4. NEVER repeat the alternative messages in your feedback, only provide feedback.

Remember, explain to {user.name} why the alternative is better and NEVER repeat the message.

At the end is a model output based on the following sample alternative message:
"I think we should reserve our spots for whale watching ahead of time to ensure we don't miss it."
{{
    "feedback": "The alternative message is better because it directly states the action to take (reserving spots) and the reason (to ensure participation). It avoids idioms that can be misunderstood, making the intention clear and leaving no room for confusion about the need to book in advance."
}}
"""

    res = await llm.generate(
        schema=FeedbackContentOnly, model=llm.Model.GPT_4o, system=system, prompt=prompt
    )

    return res.feedback
