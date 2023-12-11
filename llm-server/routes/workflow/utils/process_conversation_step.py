from json import dumps
from typing import Optional, List, cast

from langchain.schema import HumanMessage, SystemMessage, BaseMessage
from langchain.schema import OutputParserException

from custom_types.api_operation import ActionOperation_vs
from custom_types.bot_message import parse_bot_message, BotMessage
from entities.flow_entity import FlowDTO
from routes.workflow.utils.document_similarity_dto import DocumentSimilarityDTO
from utils.chat_models import CHAT_MODELS
# push it to the library
from utils.get_chat_model import get_chat_model
from utils.get_logger import CustomLogger

logger = CustomLogger(module_name=__name__)
chat = get_chat_model(CHAT_MODELS.gpt_3_5_turbo_16k)

"""
@todo
# 1. Add application initial state here as well
# 2. Add api data from qdrant so that the llm understands what apis are available to it for use
"""


def process_conversation_step(
        session_id: str,
        user_message: str,
        knowledgebase: List[DocumentSimilarityDTO],
        actions: List[DocumentSimilarityDTO],
        prev_conversations: List[BaseMessage],
        flows: List[DocumentSimilarityDTO],
        base_prompt: str
):
    # max (flows, actions, knowledge)
    # if max == flows -> execute static flow
    # if max == actions -> then execute action
    # if max == knowledge -> fetch
    # if max < 70 -> normal LLM reply or dynamic flow?



    logger.info("planner data", context=knowledgebase, api_summaries=actions, prev_conversations=prev_conversations,
                flows=flows)
    if not session_id:
        raise ValueError("Session id must be defined for chat conversations")

    messages: List[BaseMessage] = [SystemMessage(content=base_prompt), SystemMessage(
        content="You will have access to a list of api's and some useful information, called context.")]

    if len(prev_conversations) > 0:
        messages.extend(prev_conversations)

    if knowledgebase and len(actions) > 0 and len(flows) > 0:
        messages.append(
            HumanMessage(  # todo revisit this area
                content=f"Here is some relevant context I found that might be helpful - ```{dumps(knowledgebase)}```. Also, here is the excerpt from API swagger for the APIs I think might be helpful in answering the question ```{dumps(actions)}```. I also found some api flows, that maybe able to answer the following question ```{dumps(flows)}```. If one of the flows can accurately answer the question, then set `id` in the response should be the ids defined in the flows. Flows should take precedence over the api_summaries"
            )
        )

    elif knowledgebase and len(actions) > 0:
        messages.append(
            HumanMessage(
                content=f"Here is some relevant context I found that might be helpful - ```{dumps(knowledgebase)}```. Also, here is the excerpt from API swagger for the APIs I think might be helpful in answering the question ```{dumps(actions)}```. "
            )
        )
    elif knowledgebase:
        messages.append(
            HumanMessage(
                content=f"I found some relevant context that might be helpful. Here is the context: ```{dumps(knowledgebase)}```. "
            )
        )
    elif len(actions) > 0:
        messages.append(
            HumanMessage(
                content=f"I found API summaries that might be helpful in answering the question. Here are the api summaries: ```{dumps(actions)}```. "
            )
        )
    else:
        pass

    messages.append(
        HumanMessage(
            content="""Based on the information provided to you I want you to answer the questions that follow. Your should respond with a json that looks like the following, you must always use the operationIds provided in api summaries. Do not make up an operation id - 
    {
        "ids": ["list", "of", "operationIds", "for apis to be called"],
        "bot_message": "your response based on the instructions provided at the beginning",
        "missing_information": "Optional Field; Incase of ambiguity where user input is not sufficient to make the api call, ask follow up questions."
    }                
    """
        )
    )
    messages.append(
        HumanMessage(content="If you are unsure / confused, ask claryfying questions")
    )

    messages.append(HumanMessage(content=user_message))

    logger.info("messages array", messages=messages)

    content = cast(str, chat(messages=messages).content)

    try:
        d = parse_bot_message(content)
        logger.info(
            "Extracting JSON payload",
            action="parse_bot_message",
            data=d,
            content=content,
        )
        return d

    except OutputParserException as e:
        logger.warn("Failed to parse json", data=content, err=str(e))
        return BotMessage(bot_message=content, ids=[], missing_information=None)
    except Exception as e:
        logger.warn("unexpected error occured", err=str(e))
        return BotMessage(ids=[], bot_message=str(e), missing_information=None)
