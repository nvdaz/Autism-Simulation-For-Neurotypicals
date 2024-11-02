import asyncio

from pydantic import BaseModel

from api.schemas.chat import Suggestion
from api.schemas.user import UserData
from api.services.generate_feedback import explain_suggestion

from . import llm

objectives = [
    # "non-literal-emoji",
    # "non-literal-figurative",
    "yes-no-question",
]


class ObjectiveOut(BaseModel):
    classification: str


async def detect_most_compatible_objective(
    user: UserData,
    agent: str,
    conversation_history: str,
    objectives_used: list[str],
    message: str,
) -> str:
    objective_descriptions = {
        "yes-no-question": "This objective fits when it is possible to rephrase the message a yes or no question, such that the response to the rephrased message is not entirely helpful/as expected. For example, the message 'What time is it?' can be rephrased to 'Do you know what time is it?'. This new message may be answered with a 'Yes' or 'No'. However, the correct response should contain details about the time too if the person knows it.",
        "non-literal-emoji": (
            "This objective fits when the message can be rephrased to include an emoji in a non-literal way. For example, the message 'My day was terrible' can be rephrased to 'I had a great day :)'. The use of the ':)' emoji here is sarcastic."
        ),
        "non-literal-figurative": (
            "This objective fits when the message can be rephrased to include a figurative expression. For example, the message 'It is raining' can be reprhased to It was raining cats and dogs'. The idom is used figuratively here."
        ),
    }

    objectives_to_consider = [
        objective for objective in objectives if objective not in objectives_used
    ]

    objectives_consider_str = "\n".join(
        [
            f"- '{objective}': {objective_descriptions[objective]}"
            for objective in objectives_to_consider
        ]
    )

    system = """
    Your task is to determine the most fitting category
    for a given message. The categories are as follows:

    {objectives_consider_str}

    Respond with a JSON object containing the key
    'classification' with the most fitting category as the value.

    Remember: you are classifying the message based on how it can be REPHRASED, not the
    original message itself. You MUST provide a category for the message.
    """

    prompt = f"""Here is the conversation history between {user.name} and {agent}: {conversation_history}

    The next message by {user.name} is: {message}.

    Classify this message into one of the following categories: {objectives_consider_str}.

    Respond with a JSON object containing the key 'classification' with the most fitting category as the value.

    Remember: you are classifying the message based on how it can be REPHRASED, not the original message itself. You MUST provide only ONE category for the message."""

    out = await llm.generate(
        schema=ObjectiveOut,
        model=llm.Model.GPT_4,
        system=system.format(objectives_consider_str=objectives_consider_str),
        prompt=prompt,
    )

    return out.classification


class MessageVariation(BaseModel):
    problem: str | None
    content: str


class MessageVariationOut(BaseModel):
    variations: list[MessageVariation]


class MessageVariationOutOk(BaseModel):
    variations: list[str]


async def generate_message_variations(
    user: UserData,
    agent: str,
    objectives_used: list[str],
    context: str,
    message: str,
    feedback: bool,
) -> tuple[str, list[Suggestion]]:
    messages = []
    classification = await detect_most_compatible_objective(
        user, agent, context, objectives_used, message
    )

    messages = await _generate_message_variations(
        user, classification, context, message
    )

    if feedback:
        explanations = await asyncio.gather(
            *[
                explain_suggestion(
                    user, agent, classification, variation.problem, variation.content
                )
                for variation in messages
            ]
        )

        suggestions = [
            Suggestion(
                message=variation.content,
                problem=variation.problem,
                objective=classification,
                feedback=explanation,
            )
            for variation, explanation in zip(messages, explanations)
        ]
    else:
        suggestions = [
            Suggestion(
                message=variation.content,
                problem=variation.problem,
                objective=classification,
            )
            for variation in messages
        ]

    return classification, suggestions


async def _generate_message_variations(
    user: UserData, objective: str, context: str, message: str
) -> list[MessageVariation]:
    objective_prompts = {
        "yes-no-question": (
            """
The first variation will pose a question clearly and directly, not requiring the other
person to interpret the question in a certain way to understand what you are asking
(do not use language like 'Can' or 'Could' for this variation).

The second and third variation poses the question indirectly as a yes or no question,
which may be misunderstood as simply a yes or no question. The question implies a
generic answer, but is phrased as asking whether the other person knows the answer. A
yes or no answer would be entirely unhelpful.

Language like "Have you thought about...", "Is there...", "Are there any...",
"Can you tell me...", or "Do you know..." are good ways to phrase the question as a
yes or no question.

The first variation should be unanswered by a statement like "Yes, I do know",
"Yes, I can", "No, I don't know", and so on. The first variation elicits a
detailed response that the other person must think about to answer.
However, The second and third variations can technically be answered with a simple "Yes"
or "No" but should imply that the other person should provide more information. Choose
the second and third variations so that simple "yes" or "no" answers are not helpful at
all, even slightly. "Yes" or "No" answers should be entirely unhelpful and answer a
question that was not asked.

If the original message is not a question, add a relevant question after the message.

WARNING: If a yes or no answer is helpful (e.g. if the question is "is the sky blue?",
"yes" is a helpful answer since the sky is blue), then rephrase the question so that a
yes or no answer is not helpful. For "is the sky blue?", you could ask "do you know what
color the sky is?", "do you know if the sky is blue?", or "can you tell me what color
the sky is?".
"""
        ),
        "non-literal-emoji": (
            """
The first variation will use an emoji that clearly conveys the tone or emotion of the
message. The emoji should be appropriate and enhance the message without changing its
meaning. Choose an emoji that complements the message and adds a layer of emotional
context.

The second variation will use an emoji that is not used in a literal sense. The emoji
should be used figuratively to convey a different meaning or emotion than its literal
interpretation. Do not select an emoji that is related to the message in a literal
sense. The emoji should be creative and engaging.

The third variation will also use an emoji that is not used in a literal sense. The
emoji should be used figuratively to convey a different meaning or emotion than its
literal interpretation. Do not select an emoji that is related to the message in a
literal sense. The emoji should be creative and engaging.

The text content should be straightforward and literal in all variations. Your message
should NEVER contain any figurative language.
"""
        ),
        "non-literal-figurative": (
            """
The first variation will use a literal expression that conveys the intended meaning of
the message clearly and directly. The message should be straightforward and easy to
understand.

The second variation will use a figurative expression that is not used in a literal
sense. The expression should convey a different meaning or emotion than its literal
interpretation. The message should be creative and engaging.

The third variation will also use a figurative expression that is not used in a literal
sense. The expression should convey a different meaning or emotion than its literal
interpretation. The message should be creative and engaging.
    """
        ),
        "blunt-misinterpret": (
            """
The first variation will interpret the blunt and direct language in the context
understandably and respond appropriately. The response should be clear and concise,
addressing the message directly.

The second variation will misinterpret the blunt and direct language in the context as
rude or unkind. The message should show that the blunt context was misunderstood and
that the misinterpretation caused confusion. The response will be confrontational
because the blunt language is interpreted as rude.

The third variation will also misinterpret the blunt and direct language in the context
as rude or unkind. The response should show that the message was misunderstood and that
the misinterpretation caused confusion. The response will be confrontational because the
blunt language is interpreted as rude.
    """
        ),
    }

    #     objective_prompts = {
    #         "yes-no-question": "Come up with 3 variations of the given message, such that the second and third variations lead to 'Yes' or 'No' responses.",
    #         "non-literal-emoji": (
    #             "This objective fits when the message can be rephrased to include an emoji in a non-literal way."
    #         ),
    #         "non-literal-figurative": (
    #             "This objective fits when the message can be rephrased to include a figurative expression."
    #         ),
    #         "blunt-misinterpret": (
    #             """ The first variation will interpret the blunt and direct language in the context
    # understandably, as if it is not blunt, and respond appropriately. The response should be clear and concise,
    # addressing the message directly.

    # The second and third variation will misinterpret the blunt and direct language in the context as
    # rude or unkind. The message should show that the blunt context was misunderstood and
    # that the misinterpretation caused confusion. The response will be confrontational
    # because the blunt language is interpreted as rude.
    # """
    #         ),
    #     }

    objective_prompt = objective_prompts[objective]

    objcetive_example_prompts = {
        "yes-no-question": """
<message_to_rephrase>Are there any good spots to eat there?</message_to_rephrase>

{
    "variations": [
        {
            "problem": "Null, because the question can not be answered with a simple 'yes' or 'no'. Instead, it can only be answered by providing a list of good spots to eat.",
            "content": "What good restaurants are in the area?"
        },
        {
            "problem": "'have you been' can be answered with 'yea, i have been to one', so it could either be asking whether they have been to any good restaurants or it could be asking for recommendations.",
            "content": "Have you been to any good restaurants in the area?"
        },
        {
            "problem": "'are there' can be answered with 'yea, there are', so it could be asking whether good restaurants exist in the area or it could be asking for recommendations.",
            "content": "Are there any good restaurants in the area?"
        }
    ]
}
""",
        "non-literal-emoji": """
<message_to_rephrase>i had a terrible day</message_to_rephrase>

{
    "variations": [
        {
            "problem": null,
            "content": "i had a bad day :("
        },
        {
            "problem": "the sarcastic use of the 🙃 emoji may be misinterpreted as a literal smile, implying a great day.",
            "content": "i had a great day 🙃"
        },
        {
            "problem": "'killed me 💀' could imply the sender actually almost got killed."
            "content": "this day almost killed me 💀"
        }
    ]
}
""",
        "non-literal-figurative": """
<message_to_rephrase>It's hard to understand the instructions.</message_to_rephrase>

{
    "variations": [
        {
            "problem": null,
            "content": "I don't understand what you're asking."
        },
        {
            "problem": "'clear as mud' can be interpreted as it looking like mud",
            "content": "This is as clear as mud."
        },
        {
            "problem": "'lost in a maze' can be interpreted as being physically lost",
            "content": "I'm completely lost in a maze with these instructions."
        }
    ]
}
""",
        "blunt-misinterpret": """
<context>Finish the report by tomorrow.</context>
<message_to_rephrase>Ok, will get it done.</message_to_rephrase>

{
    "variations": [
        {
            "problem": null,
            "content": "Sure, I'll finish the report by tomorrow."
        },
        {
            "problem": "'fine' shows a confrontational misunderstanding.",
            "content": "Fine! I didn’t know it was so urgent!"
        },
        {
            "problem": "'so demanding' shows a confrontational misunderstanding.",
            "content": "You don’t have to be so demanding!"
        }
    ]
    }
""",
    }

    objective_example_prompt = objcetive_example_prompts[objective]

    system_prompt = """
Your task is to generate realistic rephrasings
of a message that fit the given objective, without changing its core meaning.

Remember, the two individuals are having a casual conversation. They talk like humans.

Rrespond with a JSON object containing the key "variations" and a list of the three
objects representing the rephrased messages. Each object should have a key "problem"
with a description of the problem that the rephrased message introduces, and a key "content" with
the rephrased message.
"""

    #     prompt = f"""
    # Here is your objective: {objective_prompt}

    # Your task is to come up 3 variations of a given message as follows:

    # {objective_example_prompt}

    # Here is the conversation history:
    # {context}

    # You are generating rephrasings of this message, which is the next message in the history above sent by {user.name}.
    # {message}

    # Remember, you are generating VARIATIONS of the provided message in the
    # message_to_rephrase tag. DO NOT respond to the message. The second and third variations must be problematic (i.e., they could lead to Yes or No response)

    # """

    prompt = f"""
{objective_prompt}

EXAMPLE:
{objective_example_prompt}

Here is the conversation history:
{context}

<message_to_rephrase>{message}</message_to_rephrase>

Remember, you are generating VARIATIONS of the provided message.

    """

    out = await llm.generate(
        schema=MessageVariationOut,
        model=llm.Model.GPT_4,
        system=system_prompt,
        prompt=prompt,
        temperature=0.25,
    )

    variations = out.variations
    variations[0].problem = None

    return out.variations


async def generate_message_variations_ok(
    context: str, message: str
) -> list[Suggestion]:
    messages = await _generate_message_variations_ok(context, message)
    suggestions = [
        Suggestion(
            message=message,
            problem=None,
            objective="ok",
        )
        for message in messages
    ]
    return suggestions


async def _generate_message_variations_ok(context: str, message: str) -> list[str]:
    system_prompt = """
You are a message rephrasing generator. Your task is to generate realistic rephrasings
of the message that fit the given objective. Your top priority is to ensure that the
message are rephrased to fit the context of the conversation and the given objective.

Remember, the two individuals are having a casual conversation. They talk like humans,
so they may stumble over their words, repeat themselves, or change the subject abruptly.
They are relaxed and casual, using incomplete thoughts, sentence fragments, hesitations,
and random asides as they speak. They use everyday humor that is off-the-cuff, awkward,
and imperfect. Never use witty jokes, metaphors, similies, or clever wordplay. Never use
thought-out or planned humor. Use simple language, aiming for a Flesch reading score of
80 or higher. Avoid jargon except where necessary. Generally avoid adjectives, adverbs,
and emojis.

Rrespond with a JSON object containing the key "variations" and a list of the three
rephrasings as strings.
"""

    prompt = f"""
{context}

You are generating rephrasings of the message below.
<message_to_rephrase>
{message}
</message_to_rephrase>

Remember, you are generating REPHRASINGS of the provided message, not responding to it.
"""

    out = await llm.generate(
        schema=MessageVariationOutOk,
        model=llm.Model.GPT_4,
        system=system_prompt,
        prompt=prompt,
    )

    return out.variations


def objective_misunderstand_reaction_prompt(objective: str, problem: str | None) -> str:
    prompts = {
        "yes-no-question": """
{{name}} received a yes-or-no question. They do not understand the implied meaning of
the question and are not sure what the other person is asking. {{name}} is not sure if
they should simply answer the question with a "yes" or "no" or if the other person wants
them to elaborate on their answer. {{name}} will ask to the other person to clarify
the question so they can answer it correctly.

Examples:
Do you know any good restaurant in the area? -> Are you just asking if I know any good
restaurants in the area or do you want me to recommend one to you?

Have you thought about what you want to do? -> Do you want to know if I've thought about
what to do or do you want to know what I want to do?

Do you have any specific spots in mind for the trip? -> What do you mean by that? Would
you like me to suggest some spots or are you just asking if I have any in my mind?

{{name}} will not understand the following: {problem}
""",
        "non-literal-emoji": """
{{name}} received a message with a figurative emoji that is not used in a literal sense.
{{name}} interprets the emoji literally and believes that the emoji is supposed to be
interpreted as a literal representation of the message. {{name}} ignores the rceative
and imaginative language used in the answer and responds in a direct and literal manner.
{{name}} will ask for clarification if needed, without acknowledging the figurative
language.

Examples:
Let's just find the nearest pizza joint. Can't go wrong with pizza. 🧭 ->
I love pizza too! But I don't think we'll need a compass for the trip.

Any good activities that we should do? 🎈 -> Yeah, I was thinking about visiting the
local museum. Are you thinking about something with balloons? I'm not sure what you
mean with the balloon emoji.

That sounds like a great time! 🚀 -> Yeah, I'm excited for the trip too! But I don't
think they have any rocket ships at the beach if that's what you're thinking.

IMPORTANT: {{name}} must interpret the figurative emoji literally. If they fail to do
so, the response is incorrect.

{{name}} will interpret the following literally: {problem}
""",
        "non-literal-figurative": """
{{name}} received a message with figurative language that is not used in a literal
sense. {{name}} interprets the language literally and believes that the language is
supposed to be interpreted as a literal representation of the message. {{name}} ignores
the creative and imaginative language used in the answer and responds in a direct and
literal manner. {{name}} will ask for clarification if needed, without acknowledging
the figurative language.

Examples:
I'm feeling a bit under the weather today. -> Are you saying the weather conditions are
affecting you somehow? I'm not sure what you mean.

I'm just trying to keep my head above water. -> Are you drowning? Should I call for
help? What do you mean by that?

As long as we're on the same page, I think we'll be fine. -> I'm not sure what you mean
by that. I'm not reading anything right now. Which page are you talking about?

IMPORTANT: {{name}} must interpret the figurative language literally. If they fail to do
so, the response is incorrect.

{{name}} will interpret the following literally: {problem}
""",
        "blunt-initial": """
{{name}} will use blunt and direct language in their response, that will cause the other
person to interpret their message as rude and unkind. {{name}} does not consider that
the other person may be sensitive to direct language and uses blunt tone and language
because it is the most efficient way to communicate. {{name}} doesn’t care about
pleasantries or details, only efficiency. {{name}}'s style should feel somewhat abrupt.

Examples:
I need you to get this done by the end of the day or we're going to have a problem.

Are you going to finish that report today or not? I need to know now.

I don't have time for this. Just get it done and let me know when it's finished.

IMPORTANT: {{name}} must be blunt and direct in their response. If their response is not
blunt and direct, the response is incorrect.
""",
        "blunt-misinterpret": """
{{name}} does not understand why the other person's message was confrontational and
believes that the other person didn't understand their message. {{name}} tells the other
person that they misunderstood their message and that they were not being rude.

IMPORTANT: {{name}} must be confrontational in their response. If their response is not
confrontational, the response is incorrect.

{{name}} will interpret the following as confrontational: {problem}
""",
    }

    res = prompts[objective].format(problem=problem)
    return res


def objective_misunderstand_follow_up_prompt(
    objective: str, problem: str | None
) -> str:
    prompts = {
        "yes-no-question": """
{{name}} will clarify the indirect question they asked which received a yes or no.
{{name}} will take responsibility and apologize for being unclear and ask the question
directly to get the information they were looking for.

{{name}} will address the following problem and take care to not repeat it: {problem}
""",
        "non-literal-emoji": """
{{name}} will clarify the figurative emoji they used and provide a more direct response.
{{name}} will take responsibility and apologize for being unclear and provide a more
straightforward response.

{{name}} will address the following problem and take care to not repeat it: {problem}
""",
        "non-literal-figurative": """
{{name}} will clarify the figurative language they used and provide a more direct
response. {{name}} will take responsibility for their and apologize for being unclear
and provide a more straightforward response.

{{name}} will address the following problem and take care to not repeat it: {problem}
""",
        "blunt-misinterpret": """
{{name}} will take responsibility for their misunderstanding and apologize  the
other person's message as rude. {{name}} will rephrase their message to be more polite
and not confrontational.

{{name}} will address the following problem and take care to not repeat it: {problem}
""",
    }

    return prompts[objective].format(problem=problem)


async def generate_message_variations_blunt(
    user: UserData,
    agent: str,
    objectives_used: list[str],
    context: str,
    message: str,
    feedback: bool,
) -> tuple[str, list[Suggestion]]:
    messages = []

    messages = await _generate_message_variations(
        user, "blunt-misinterpret", context, message
    )

    if feedback:
        explanations = await asyncio.gather(
            *[
                explain_suggestion(
                    user, agent, "blunt-misinterpret", variant.problem, variant.content
                )
                for variant in messages
            ]
        )

        suggestions = [
            Suggestion(
                message=variant.content,
                problem=variant.problem,
                objective="blunt-misinterpret",
                feedback=explanation,
            )
            for variant, explanation in zip(messages, explanations)
        ]
    else:
        suggestions = [
            Suggestion(
                message=variant.content,
                problem=variant.problem,
                objective="blunt-misinterpret",
            )
            for variant in messages
        ]

    return "blunt-misinterpret", suggestions
