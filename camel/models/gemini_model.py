# ========= Copyright 2023-2024 @ CAMEL-AI.org. All Rights Reserved. =========
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ========= Copyright 2023-2024 @ CAMEL-AI.org. All Rights Reserved. =========
import os
from typing import Any, Dict, List, Optional, Type, Union

from openai import AsyncStream, Stream
from pydantic import BaseModel

from camel.configs import Gemini_API_PARAMS, GeminiConfig
from camel.messages import OpenAIMessage
from camel.models.openai_compatible_model import OpenAICompatibleModel
from camel.types import (
    ChatCompletion,
    ChatCompletionChunk,
    ModelType,
)
from camel.utils import (
    BaseTokenCounter,
    api_keys_required,
    get_current_agent_session_id,
    update_langfuse_trace,
)

if os.environ.get("LANGFUSE_ENABLED", "False").lower() == "true":
    try:
        from langfuse.decorators import observe
    except ImportError:
        from camel.utils import observe
elif os.environ.get("TRACEROOT_ENABLED", "False").lower() == "true":
    try:
        from traceroot import trace as observe  # type: ignore[import]
    except ImportError:
        from camel.utils import observe
else:
    from camel.utils import observe


class GeminiModel(OpenAICompatibleModel):
    r"""Gemini API in a unified OpenAICompatibleModel interface.

    Args:
        model_type (Union[ModelType, str]): Model for which a backend is
            created, one of Gemini series.
        model_config_dict (Optional[Dict[str, Any]], optional): A dictionary
            that will be fed into:obj:`openai.ChatCompletion.create()`. If
            :obj:`None`, :obj:`GeminiConfig().as_dict()` will be used.
            (default: :obj:`None`)
        api_key (Optional[str], optional): The API key for authenticating with
            the Gemini service. (default: :obj:`None`)
        url (Optional[str], optional): The url to the Gemini service.
            (default: :obj:`https://generativelanguage.googleapis.com/v1beta/
            openai/`)
        token_counter (Optional[BaseTokenCounter], optional): Token counter to
            use for the model. If not provided, :obj:`OpenAITokenCounter(
            ModelType.GPT_4O_MINI)` will be used.
            (default: :obj:`None`)
        timeout (Optional[float], optional): The timeout value in seconds for
            API calls. If not provided, will fall back to the MODEL_TIMEOUT
            environment variable or default to 180 seconds.
            (default: :obj:`None`)
        max_retries (int, optional): Maximum number of retries for API calls.
            (default: :obj:`3`)
        **kwargs (Any): Additional arguments to pass to the client
            initialization.
    """

    @api_keys_required(
        [
            ("api_key", 'GEMINI_API_KEY'),
        ]
    )
    def __init__(
        self,
        model_type: Union[ModelType, str],
        model_config_dict: Optional[Dict[str, Any]] = None,
        api_key: Optional[str] = None,
        url: Optional[str] = None,
        token_counter: Optional[BaseTokenCounter] = None,
        timeout: Optional[float] = None,
        max_retries: int = 3,
        **kwargs: Any,
    ) -> None:
        if model_config_dict is None:
            model_config_dict = GeminiConfig().as_dict()
        api_key = api_key or os.environ.get("GEMINI_API_KEY")
        url = url or os.environ.get(
            "GEMINI_API_BASE_URL",
            "https://generativelanguage.googleapis.com/v1beta/openai/",
        )
        timeout = timeout or float(os.environ.get("MODEL_TIMEOUT", 180))
        super().__init__(
            model_type=model_type,
            model_config_dict=model_config_dict,
            api_key=api_key,
            url=url,
            token_counter=token_counter,
            timeout=timeout,
            max_retries=max_retries,
            **kwargs,
        )

    def _process_messages(self, messages) -> List[OpenAIMessage]:
        r"""Process the messages for Gemini API to ensure no empty content,
        which is not accepted by Gemini.
        """
        processed_messages = []
        for msg in messages:
            msg_copy = msg.copy()
            if 'content' in msg_copy and msg_copy['content'] == '':
                msg_copy['content'] = 'null'
            processed_messages.append(msg_copy)
        return processed_messages

    @observe()
    def _run(
        self,
        messages: List[OpenAIMessage],
        response_format: Optional[Type[BaseModel]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Union[ChatCompletion, Stream[ChatCompletionChunk]]:
        r"""Runs inference of Gemini chat completion.

        Args:
            messages (List[OpenAIMessage]): Message list with the chat history
                in OpenAI API format.
            response_format (Optional[Type[BaseModel]]): The format of the
                response.
            tools (Optional[List[Dict[str, Any]]]): The schema of the tools to
                use for the request.

        Returns:
            Union[ChatCompletion, Stream[ChatCompletionChunk]]:
                `ChatCompletion` in the non-stream mode, or
                `Stream[ChatCompletionChunk]` in the stream mode.
        """

        # Update Langfuse trace with current agent session and metadata
        agent_session_id = get_current_agent_session_id()
        if agent_session_id:
            update_langfuse_trace(
                session_id=agent_session_id,
                metadata={
                    "agent_id": agent_session_id,
                    "model_type": str(self.model_type),
                },
                tags=["CAMEL-AI", str(self.model_type)],
            )

        response_format = response_format or self.model_config_dict.get(
            "response_format", None
        )
        messages = self._process_messages(messages)
        if response_format:
            if tools:
                raise ValueError(
                    "Gemini does not support function calling with "
                    "response format."
                )
            result: Union[ChatCompletion, Stream[ChatCompletionChunk]] = (
                self._request_parse(messages, response_format)
            )
        else:
            result = self._request_chat_completion(messages, tools)

        return result

    @observe()
    async def _arun(
        self,
        messages: List[OpenAIMessage],
        response_format: Optional[Type[BaseModel]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Union[ChatCompletion, AsyncStream[ChatCompletionChunk]]:
        r"""Runs inference of OpenAI chat completion in async mode.

        Args:
            messages (List[OpenAIMessage]): Message list with the chat history
                in OpenAI API format.
            response_format (Optional[Type[BaseModel]]): The format of the
                response.
            tools (Optional[List[Dict[str, Any]]]): The schema of the tools to
                use for the request.

        Returns:
            Union[ChatCompletion, AsyncStream[ChatCompletionChunk]]:
                `ChatCompletion` in the non-stream mode, or
                `AsyncStream[ChatCompletionChunk]` in the stream mode.
        """

        # Update Langfuse trace with current agent session and metadata
        agent_session_id = get_current_agent_session_id()
        if agent_session_id:
            update_langfuse_trace(
                session_id=agent_session_id,
                metadata={
                    "agent_id": agent_session_id,
                    "model_type": str(self.model_type),
                },
                tags=["CAMEL-AI", str(self.model_type)],
            )

        response_format = response_format or self.model_config_dict.get(
            "response_format", None
        )
        messages = self._process_messages(messages)
        if response_format:
            if tools:
                raise ValueError(
                    "Gemini does not support function calling with "
                    "response format."
                )
            result: Union[
                ChatCompletion, AsyncStream[ChatCompletionChunk]
            ] = await self._arequest_parse(messages, response_format)
        else:
            result = await self._arequest_chat_completion(messages, tools)

        return result

    def _request_chat_completion(
        self,
        messages: List[OpenAIMessage],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Union[ChatCompletion, Stream[ChatCompletionChunk]]:
        import copy

        request_config = copy.deepcopy(self.model_config_dict)
        # Remove strict and anyOf from each tool's function parameters since
        # Gemini does not support them
        if tools:
            for tool in tools:
                function_dict = tool.get('function', {})
                function_dict.pop("strict", None)

                # Process parameters to remove anyOf and handle enum/format
                if 'parameters' in function_dict:
                    params = function_dict['parameters']
                    if 'properties' in params:
                        for prop_name, prop_value in params[
                            'properties'
                        ].items():
                            if 'anyOf' in prop_value:
                                # Replace anyOf with the first type in the list
                                first_type = prop_value['anyOf'][0]
                                params['properties'][prop_name] = first_type
                                # Preserve description if it exists
                                if 'description' in prop_value:
                                    params['properties'][prop_name][
                                        'description'
                                    ] = prop_value['description']

                            # Handle enum and format restrictions for Gemini
                            # API enum: only allowed for string type
                            if prop_value.get('type') != 'string':
                                prop_value.pop('enum', None)

                            # format: only allowed for string, integer, and
                            # number types
                            if prop_value.get('type') not in [
                                'string',
                                'integer',
                                'number',
                            ]:
                                prop_value.pop('format', None)

            request_config["tools"] = tools

        return self._client.chat.completions.create(
            messages=messages,
            model=self.model_type,
            **request_config,
        )

    async def _arequest_chat_completion(
        self,
        messages: List[OpenAIMessage],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Union[ChatCompletion, AsyncStream[ChatCompletionChunk]]:
        import copy

        request_config = copy.deepcopy(self.model_config_dict)
        # Remove strict and anyOf from each tool's function parameters since
        # Gemini does not support them
        if tools:
            for tool in tools:
                function_dict = tool.get('function', {})
                function_dict.pop("strict", None)

                # Process parameters to remove anyOf and handle enum/format
                if 'parameters' in function_dict:
                    params = function_dict['parameters']
                    if 'properties' in params:
                        for prop_name, prop_value in params[
                            'properties'
                        ].items():
                            if 'anyOf' in prop_value:
                                # Replace anyOf with the first type in the list
                                first_type = prop_value['anyOf'][0]
                                params['properties'][prop_name] = first_type
                                # Preserve description if it exists
                                if 'description' in prop_value:
                                    params['properties'][prop_name][
                                        'description'
                                    ] = prop_value['description']

                            # Handle enum and format restrictions for Gemini
                            # API enum: only allowed for string type
                            if prop_value.get('type') != 'string':
                                prop_value.pop('enum', None)

                            # format: only allowed for string, integer, and
                            # number types
                            if prop_value.get('type') not in [
                                'string',
                                'integer',
                                'number',
                            ]:
                                prop_value.pop('format', None)

            request_config["tools"] = tools

        return await self._async_client.chat.completions.create(
            messages=messages,
            model=self.model_type,
            **request_config,
        )

    def check_model_config(self):
        r"""Check whether the model configuration contains any
        unexpected arguments to Gemini API.

        Raises:
            ValueError: If the model configuration dictionary contains any
                unexpected arguments to Gemini API.
        """
        for param in self.model_config_dict:
            if param not in Gemini_API_PARAMS:
                raise ValueError(
                    f"Unexpected argument `{param}` is "
                    "input into Gemini model backend."
                )
