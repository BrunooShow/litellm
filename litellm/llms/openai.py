from typing import (
    Optional,
    Union,
    Any,
    BinaryIO,
    Literal,
    Iterable,
)
from typing_extensions import override
from pydantic import BaseModel
import types, time, json, traceback
import httpx
from .base import BaseLLM
from litellm.utils import (
    ModelResponse,
    Choices,
    Message,
    CustomStreamWrapper,
    convert_to_model_response_object,
    Usage,
    TranscriptionResponse,
    TextCompletionResponse,
)
from typing import Callable, Optional
import litellm
from .prompt_templates.factory import prompt_factory, custom_prompt
from openai import OpenAI, AsyncOpenAI
from ..types.llms.openai import *


class OpenAIError(Exception):
    def __init__(
        self,
        status_code,
        message,
        request: Optional[httpx.Request] = None,
        response: Optional[httpx.Response] = None,
    ):
        self.status_code = status_code
        self.message = message
        if request:
            self.request = request
        else:
            self.request = httpx.Request(method="POST", url="https://api.openai.com/v1")
        if response:
            self.response = response
        else:
            self.response = httpx.Response(
                status_code=status_code, request=self.request
            )
        super().__init__(
            self.message
        )  # Call the base class constructor with the parameters it needs


class MistralConfig:
    """
    Reference: https://docs.mistral.ai/api/

    The class `MistralConfig` provides configuration for the Mistral's Chat API interface. Below are the parameters:

    - `temperature` (number or null): Defines the sampling temperature to use, varying between 0 and 2. API Default - 0.7.

    - `top_p` (number or null): An alternative to sampling with temperature, used for nucleus sampling. API Default - 1.

    - `max_tokens` (integer or null): This optional parameter helps to set the maximum number of tokens to generate in the chat completion. API Default - null.

    - `tools` (list or null): A list of available tools for the model. Use this to specify functions for which the model can generate JSON inputs.

    - `tool_choice` (string - 'auto'/'any'/'none' or null): Specifies if/how functions are called. If set to none the model won't call a function and will generate a message instead. If set to auto the model can choose to either generate a message or call a function. If set to any the model is forced to call a function. Default - 'auto'.

    - `random_seed` (integer or null): The seed to use for random sampling. If set, different calls will generate deterministic results.

    - `safe_prompt` (boolean): Whether to inject a safety prompt before all conversations. API Default - 'false'.

    - `response_format` (object or null): An object specifying the format that the model must output. Setting to { "type": "json_object" } enables JSON mode, which guarantees the message the model generates is in JSON. When using JSON mode you MUST also instruct the model to produce JSON yourself with a system or a user message.
    """

    temperature: Optional[int] = None
    top_p: Optional[int] = None
    max_tokens: Optional[int] = None
    tools: Optional[list] = None
    tool_choice: Optional[Literal["auto", "any", "none"]] = None
    random_seed: Optional[int] = None
    safe_prompt: Optional[bool] = None
    response_format: Optional[dict] = None

    def __init__(
        self,
        temperature: Optional[int] = None,
        top_p: Optional[int] = None,
        max_tokens: Optional[int] = None,
        tools: Optional[list] = None,
        tool_choice: Optional[Literal["auto", "any", "none"]] = None,
        random_seed: Optional[int] = None,
        safe_prompt: Optional[bool] = None,
        response_format: Optional[dict] = None,
    ) -> None:
        locals_ = locals().copy()
        for key, value in locals_.items():
            if key != "self" and value is not None:
                setattr(self.__class__, key, value)

    @classmethod
    def get_config(cls):
        return {
            k: v
            for k, v in cls.__dict__.items()
            if not k.startswith("__")
            and not isinstance(
                v,
                (
                    types.FunctionType,
                    types.BuiltinFunctionType,
                    classmethod,
                    staticmethod,
                ),
            )
            and v is not None
        }

    def get_supported_openai_params(self):
        return [
            "stream",
            "temperature",
            "top_p",
            "max_tokens",
            "tools",
            "tool_choice",
            "seed",
            "response_format",
        ]

    def _map_tool_choice(self, tool_choice: str) -> str:
        if tool_choice == "auto" or tool_choice == "none":
            return tool_choice
        elif tool_choice == "required":
            return "any"
        else:  # openai 'tool_choice' object param not supported by Mistral API
            return "any"

    def map_openai_params(self, non_default_params: dict, optional_params: dict):
        for param, value in non_default_params.items():
            if param == "max_tokens":
                optional_params["max_tokens"] = value
            if param == "tools":
                optional_params["tools"] = value
            if param == "stream" and value == True:
                optional_params["stream"] = value
            if param == "temperature":
                optional_params["temperature"] = value
            if param == "top_p":
                optional_params["top_p"] = value
            if param == "tool_choice" and isinstance(value, str):
                optional_params["tool_choice"] = self._map_tool_choice(
                    tool_choice=value
                )
            if param == "seed":
                optional_params["extra_body"] = {"random_seed": value}
            if param == "response_format":
                optional_params["response_format"] = value
        return optional_params


class DeepInfraConfig:
    """
    Reference: https://deepinfra.com/docs/advanced/openai_api

    The class `DeepInfra` provides configuration for the DeepInfra's Chat Completions API interface. Below are the parameters:
    """

    frequency_penalty: Optional[int] = None
    function_call: Optional[Union[str, dict]] = None
    functions: Optional[list] = None
    logit_bias: Optional[dict] = None
    max_tokens: Optional[int] = None
    n: Optional[int] = None
    presence_penalty: Optional[int] = None
    stop: Optional[Union[str, list]] = None
    temperature: Optional[int] = None
    top_p: Optional[int] = None
    response_format: Optional[dict] = None
    tools: Optional[list] = None
    tool_choice: Optional[Union[str, dict]] = None

    def __init__(
        self,
        frequency_penalty: Optional[int] = None,
        function_call: Optional[Union[str, dict]] = None,
        functions: Optional[list] = None,
        logit_bias: Optional[dict] = None,
        max_tokens: Optional[int] = None,
        n: Optional[int] = None,
        presence_penalty: Optional[int] = None,
        stop: Optional[Union[str, list]] = None,
        temperature: Optional[int] = None,
        top_p: Optional[int] = None,
        response_format: Optional[dict] = None,
        tools: Optional[list] = None,
        tool_choice: Optional[Union[str, dict]] = None,
    ) -> None:
        locals_ = locals().copy()
        for key, value in locals_.items():
            if key != "self" and value is not None:
                setattr(self.__class__, key, value)

    @classmethod
    def get_config(cls):
        return {
            k: v
            for k, v in cls.__dict__.items()
            if not k.startswith("__")
            and not isinstance(
                v,
                (
                    types.FunctionType,
                    types.BuiltinFunctionType,
                    classmethod,
                    staticmethod,
                ),
            )
            and v is not None
        }

    def get_supported_openai_params(self):
        return [
            "stream",
            "frequency_penalty",
            "function_call",
            "functions",
            "logit_bias",
            "max_tokens",
            "n",
            "presence_penalty",
            "stop",
            "temperature",
            "top_p",
            "response_format",
            "tools",
            "tool_choice",
        ]

    def map_openai_params(
        self, non_default_params: dict, optional_params: dict, model: str
    ):
        supported_openai_params = self.get_supported_openai_params()
        for param, value in non_default_params.items():
            if (
                param == "temperature"
                and value == 0
                and model == "mistralai/Mistral-7B-Instruct-v0.1"
            ):  # this model does no support temperature == 0
                value = 0.0001  # close to 0
            if param in supported_openai_params:
                optional_params[param] = value
        return optional_params


class OpenAIConfig:
    """
    Reference: https://platform.openai.com/docs/api-reference/chat/create

    The class `OpenAIConfig` provides configuration for the OpenAI's Chat API interface. Below are the parameters:

    - `frequency_penalty` (number or null): Defaults to 0. Allows a value between -2.0 and 2.0. Positive values penalize new tokens based on their existing frequency in the text so far, thereby minimizing repetition.

    - `function_call` (string or object): This optional parameter controls how the model calls functions.

    - `functions` (array): An optional parameter. It is a list of functions for which the model may generate JSON inputs.

    - `logit_bias` (map): This optional parameter modifies the likelihood of specified tokens appearing in the completion.

    - `max_tokens` (integer or null): This optional parameter helps to set the maximum number of tokens to generate in the chat completion.

    - `n` (integer or null): This optional parameter helps to set how many chat completion choices to generate for each input message.

    - `presence_penalty` (number or null): Defaults to 0. It penalizes new tokens based on if they appear in the text so far, hence increasing the model's likelihood to talk about new topics.

    - `stop` (string / array / null): Specifies up to 4 sequences where the API will stop generating further tokens.

    - `temperature` (number or null): Defines the sampling temperature to use, varying between 0 and 2.

    - `top_p` (number or null): An alternative to sampling with temperature, used for nucleus sampling.
    """

    frequency_penalty: Optional[int] = None
    function_call: Optional[Union[str, dict]] = None
    functions: Optional[list] = None
    logit_bias: Optional[dict] = None
    max_tokens: Optional[int] = None
    n: Optional[int] = None
    presence_penalty: Optional[int] = None
    stop: Optional[Union[str, list]] = None
    temperature: Optional[int] = None
    top_p: Optional[int] = None
    response_format: Optional[dict] = None

    def __init__(
        self,
        frequency_penalty: Optional[int] = None,
        function_call: Optional[Union[str, dict]] = None,
        functions: Optional[list] = None,
        logit_bias: Optional[dict] = None,
        max_tokens: Optional[int] = None,
        n: Optional[int] = None,
        presence_penalty: Optional[int] = None,
        stop: Optional[Union[str, list]] = None,
        temperature: Optional[int] = None,
        top_p: Optional[int] = None,
        response_format: Optional[dict] = None,
    ) -> None:
        locals_ = locals().copy()
        for key, value in locals_.items():
            if key != "self" and value is not None:
                setattr(self.__class__, key, value)

    @classmethod
    def get_config(cls):
        return {
            k: v
            for k, v in cls.__dict__.items()
            if not k.startswith("__")
            and not isinstance(
                v,
                (
                    types.FunctionType,
                    types.BuiltinFunctionType,
                    classmethod,
                    staticmethod,
                ),
            )
            and v is not None
        }

    def get_supported_openai_params(self, model: str) -> list:
        base_params = [
            "frequency_penalty",
            "logit_bias",
            "logprobs",
            "top_logprobs",
            "max_tokens",
            "n",
            "presence_penalty",
            "seed",
            "stop",
            "stream",
            "stream_options",
            "temperature",
            "top_p",
            "tools",
            "tool_choice",
            "user",
            "function_call",
            "functions",
            "max_retries",
            "extra_headers",
        ]  # works across all models

        model_specific_params = []
        if (
            model != "gpt-3.5-turbo-16k" and model != "gpt-4"
        ):  # gpt-4 does not support 'response_format'
            model_specific_params.append("response_format")

        return base_params + model_specific_params

    def map_openai_params(
        self, non_default_params: dict, optional_params: dict, model: str
    ) -> dict:
        supported_openai_params = self.get_supported_openai_params(model)
        for param, value in non_default_params.items():
            if param in supported_openai_params:
                optional_params[param] = value
        return optional_params


class OpenAITextCompletionConfig:
    """
    Reference: https://platform.openai.com/docs/api-reference/completions/create

    The class `OpenAITextCompletionConfig` provides configuration for the OpenAI's text completion API interface. Below are the parameters:

    - `best_of` (integer or null): This optional parameter generates server-side completions and returns the one with the highest log probability per token.

    - `echo` (boolean or null): This optional parameter will echo back the prompt in addition to the completion.

    - `frequency_penalty` (number or null): Defaults to 0. It is a numbers from -2.0 to 2.0, where positive values decrease the model's likelihood to repeat the same line.

    - `logit_bias` (map): This optional parameter modifies the likelihood of specified tokens appearing in the completion.

    - `logprobs` (integer or null): This optional parameter includes the log probabilities on the most likely tokens as well as the chosen tokens.

    - `max_tokens` (integer or null): This optional parameter sets the maximum number of tokens to generate in the completion.

    - `n` (integer or null): This optional parameter sets how many completions to generate for each prompt.

    - `presence_penalty` (number or null): Defaults to 0 and can be between -2.0 and 2.0. Positive values increase the model's likelihood to talk about new topics.

    - `stop` (string / array / null): Specifies up to 4 sequences where the API will stop generating further tokens.

    - `suffix` (string or null): Defines the suffix that comes after a completion of inserted text.

    - `temperature` (number or null): This optional parameter defines the sampling temperature to use.

    - `top_p` (number or null): An alternative to sampling with temperature, used for nucleus sampling.
    """

    best_of: Optional[int] = None
    echo: Optional[bool] = None
    frequency_penalty: Optional[int] = None
    logit_bias: Optional[dict] = None
    logprobs: Optional[int] = None
    max_tokens: Optional[int] = None
    n: Optional[int] = None
    presence_penalty: Optional[int] = None
    stop: Optional[Union[str, list]] = None
    suffix: Optional[str] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None

    def __init__(
        self,
        best_of: Optional[int] = None,
        echo: Optional[bool] = None,
        frequency_penalty: Optional[int] = None,
        logit_bias: Optional[dict] = None,
        logprobs: Optional[int] = None,
        max_tokens: Optional[int] = None,
        n: Optional[int] = None,
        presence_penalty: Optional[int] = None,
        stop: Optional[Union[str, list]] = None,
        suffix: Optional[str] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
    ) -> None:
        locals_ = locals().copy()
        for key, value in locals_.items():
            if key != "self" and value is not None:
                setattr(self.__class__, key, value)

    @classmethod
    def get_config(cls):
        return {
            k: v
            for k, v in cls.__dict__.items()
            if not k.startswith("__")
            and not isinstance(
                v,
                (
                    types.FunctionType,
                    types.BuiltinFunctionType,
                    classmethod,
                    staticmethod,
                ),
            )
            and v is not None
        }

    def convert_to_chat_model_response_object(
        self,
        response_object: Optional[TextCompletionResponse] = None,
        model_response_object: Optional[ModelResponse] = None,
    ):
        try:
            ## RESPONSE OBJECT
            if response_object is None or model_response_object is None:
                raise ValueError("Error in response object format")
            choice_list = []
            for idx, choice in enumerate(response_object["choices"]):
                message = Message(
                    content=choice["text"],
                    role="assistant",
                )
                choice = Choices(
                    finish_reason=choice["finish_reason"], index=idx, message=message
                )
                choice_list.append(choice)
            model_response_object.choices = choice_list

            if "usage" in response_object:
                setattr(model_response_object, "usage", response_object["usage"])

            if "id" in response_object:
                model_response_object.id = response_object["id"]

            if "model" in response_object:
                model_response_object.model = response_object["model"]

            model_response_object._hidden_params["original_response"] = (
                response_object  # track original response, if users make a litellm.text_completion() request, we can return the original response
            )
            return model_response_object
        except Exception as e:
            raise e


class OpenAIChatCompletion(BaseLLM):
    def __init__(self) -> None:
        super().__init__()

    def completion(
        self,
        model_response: ModelResponse,
        timeout: Union[float, httpx.Timeout],
        optional_params: dict,
        model: Optional[str] = None,
        messages: Optional[list] = None,
        print_verbose: Optional[Callable] = None,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        acompletion: bool = False,
        logging_obj=None,
        litellm_params=None,
        logger_fn=None,
        headers: Optional[dict] = None,
        custom_prompt_dict: dict = {},
        client=None,
        organization: Optional[str] = None,
        custom_llm_provider: Optional[str] = None,
    ):
        super().completion()
        exception_mapping_worked = False
        try:
            if headers:
                optional_params["extra_headers"] = headers
            if model is None or messages is None:
                raise OpenAIError(status_code=422, message=f"Missing model or messages")

            if not isinstance(timeout, float) and not isinstance(
                timeout, httpx.Timeout
            ):
                raise OpenAIError(
                    status_code=422,
                    message=f"Timeout needs to be a float or httpx.Timeout",
                )

            if custom_llm_provider != "openai":
                model_response.model = f"{custom_llm_provider}/{model}"
                # process all OpenAI compatible provider logic here
                if custom_llm_provider == "mistral":
                    # check if message content passed in as list, and not string
                    messages = prompt_factory(
                        model=model,
                        messages=messages,
                        custom_llm_provider=custom_llm_provider,
                    )
                if custom_llm_provider == "perplexity" and messages is not None:
                    # check if messages.name is passed + supported, if not supported remove
                    messages = prompt_factory(
                        model=model,
                        messages=messages,
                        custom_llm_provider=custom_llm_provider,
                    )

            for _ in range(
                2
            ):  # if call fails due to alternating messages, retry with reformatted message
                data = {"model": model, "messages": messages, **optional_params}

                try:
                    max_retries = data.pop("max_retries", 2)
                    if acompletion is True:
                        if optional_params.get("stream", False):
                            return self.async_streaming(
                                logging_obj=logging_obj,
                                headers=headers,
                                data=data,
                                model=model,
                                api_base=api_base,
                                api_key=api_key,
                                timeout=timeout,
                                client=client,
                                max_retries=max_retries,
                                organization=organization,
                            )
                        else:
                            return self.acompletion(
                                data=data,
                                headers=headers,
                                logging_obj=logging_obj,
                                model_response=model_response,
                                api_base=api_base,
                                api_key=api_key,
                                timeout=timeout,
                                client=client,
                                max_retries=max_retries,
                                organization=organization,
                            )
                    elif optional_params.get("stream", False):
                        return self.streaming(
                            logging_obj=logging_obj,
                            headers=headers,
                            data=data,
                            model=model,
                            api_base=api_base,
                            api_key=api_key,
                            timeout=timeout,
                            client=client,
                            max_retries=max_retries,
                            organization=organization,
                        )
                    else:
                        if not isinstance(max_retries, int):
                            raise OpenAIError(
                                status_code=422, message="max retries must be an int"
                            )
                        if client is None:
                            openai_client = OpenAI(
                                api_key=api_key,
                                base_url=api_base,
                                http_client=litellm.client_session,
                                timeout=timeout,
                                max_retries=max_retries,
                                organization=organization,
                            )
                        else:
                            openai_client = client

                        ## LOGGING
                        logging_obj.pre_call(
                            input=messages,
                            api_key=openai_client.api_key,
                            additional_args={
                                "headers": headers,
                                "api_base": openai_client._base_url._uri_reference,
                                "acompletion": acompletion,
                                "complete_input_dict": data,
                            },
                        )

                        response = openai_client.chat.completions.create(**data, timeout=timeout)  # type: ignore
                        stringified_response = response.model_dump()
                        logging_obj.post_call(
                            input=messages,
                            api_key=api_key,
                            original_response=stringified_response,
                            additional_args={"complete_input_dict": data},
                        )
                        return convert_to_model_response_object(
                            response_object=stringified_response,
                            model_response_object=model_response,
                        )
                except Exception as e:
                    if print_verbose is not None:
                        print_verbose(f"openai.py: Received openai error - {str(e)}")
                    if (
                        "Conversation roles must alternate user/assistant" in str(e)
                        or "user and assistant roles should be alternating" in str(e)
                    ) and messages is not None:
                        if print_verbose is not None:
                            print_verbose("openai.py: REFORMATS THE MESSAGE!")
                        # reformat messages to ensure user/assistant are alternating, if there's either 2 consecutive 'user' messages or 2 consecutive 'assistant' message, add a blank 'user' or 'assistant' message to ensure compatibility
                        new_messages = []
                        for i in range(len(messages) - 1):  # type: ignore
                            new_messages.append(messages[i])
                            if messages[i]["role"] == messages[i + 1]["role"]:
                                if messages[i]["role"] == "user":
                                    new_messages.append(
                                        {"role": "assistant", "content": ""}
                                    )
                                else:
                                    new_messages.append({"role": "user", "content": ""})
                        new_messages.append(messages[-1])
                        messages = new_messages
                    elif (
                        "Last message must have role `user`" in str(e)
                    ) and messages is not None:
                        new_messages = messages
                        new_messages.append({"role": "user", "content": ""})
                        messages = new_messages
                    else:
                        raise e
        except OpenAIError as e:
            exception_mapping_worked = True
            raise e
        except Exception as e:
            if hasattr(e, "status_code"):
                raise OpenAIError(status_code=e.status_code, message=str(e))
            else:
                raise OpenAIError(status_code=500, message=traceback.format_exc())

    async def acompletion(
        self,
        data: dict,
        model_response: ModelResponse,
        timeout: Union[float, httpx.Timeout],
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        organization: Optional[str] = None,
        client=None,
        max_retries=None,
        logging_obj=None,
        headers=None,
    ):
        response = None
        try:
            if client is None:
                openai_aclient = AsyncOpenAI(
                    api_key=api_key,
                    base_url=api_base,
                    http_client=litellm.aclient_session,
                    timeout=timeout,
                    max_retries=max_retries,
                    organization=organization,
                )
            else:
                openai_aclient = client

            ## LOGGING
            logging_obj.pre_call(
                input=data["messages"],
                api_key=openai_aclient.api_key,
                additional_args={
                    "headers": {"Authorization": f"Bearer {openai_aclient.api_key}"},
                    "api_base": openai_aclient._base_url._uri_reference,
                    "acompletion": True,
                    "complete_input_dict": data,
                },
            )

            response = await openai_aclient.chat.completions.create(
                **data, timeout=timeout
            )
            stringified_response = response.model_dump()
            logging_obj.post_call(
                input=data["messages"],
                api_key=api_key,
                original_response=stringified_response,
                additional_args={"complete_input_dict": data},
            )
            return convert_to_model_response_object(
                response_object=stringified_response,
                model_response_object=model_response,
            )
        except Exception as e:
            raise e

    def streaming(
        self,
        logging_obj,
        timeout: Union[float, httpx.Timeout],
        data: dict,
        model: str,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        organization: Optional[str] = None,
        client=None,
        max_retries=None,
        headers=None,
    ):
        if client is None:
            openai_client = OpenAI(
                api_key=api_key,
                base_url=api_base,
                http_client=litellm.client_session,
                timeout=timeout,
                max_retries=max_retries,
                organization=organization,
            )
        else:
            openai_client = client
        ## LOGGING
        logging_obj.pre_call(
            input=data["messages"],
            api_key=api_key,
            additional_args={
                "headers": {"Authorization": f"Bearer {openai_client.api_key}"},
                "api_base": openai_client._base_url._uri_reference,
                "acompletion": False,
                "complete_input_dict": data,
            },
        )
        response = openai_client.chat.completions.create(**data, timeout=timeout)
        streamwrapper = CustomStreamWrapper(
            completion_stream=response,
            model=model,
            custom_llm_provider="openai",
            logging_obj=logging_obj,
            stream_options=data.get("stream_options", None),
        )
        return streamwrapper

    async def async_streaming(
        self,
        logging_obj,
        timeout: Union[float, httpx.Timeout],
        data: dict,
        model: str,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        organization: Optional[str] = None,
        client=None,
        max_retries=None,
        headers=None,
    ):
        response = None
        try:
            if client is None:
                openai_aclient = AsyncOpenAI(
                    api_key=api_key,
                    base_url=api_base,
                    http_client=litellm.aclient_session,
                    timeout=timeout,
                    max_retries=max_retries,
                    organization=organization,
                )
            else:
                openai_aclient = client
            ## LOGGING
            logging_obj.pre_call(
                input=data["messages"],
                api_key=api_key,
                additional_args={
                    "headers": headers,
                    "api_base": api_base,
                    "acompletion": True,
                    "complete_input_dict": data,
                },
            )

            response = await openai_aclient.chat.completions.create(
                **data, timeout=timeout
            )
            streamwrapper = CustomStreamWrapper(
                completion_stream=response,
                model=model,
                custom_llm_provider="openai",
                logging_obj=logging_obj,
                stream_options=data.get("stream_options", None),
            )
            return streamwrapper
        except (
            Exception
        ) as e:  # need to exception handle here. async exceptions don't get caught in sync functions.
            if response is not None and hasattr(response, "text"):
                raise OpenAIError(
                    status_code=500,
                    message=f"{str(e)}\n\nOriginal Response: {response.text}",
                )
            else:
                if type(e).__name__ == "ReadTimeout":
                    raise OpenAIError(status_code=408, message=f"{type(e).__name__}")
                elif hasattr(e, "status_code"):
                    raise OpenAIError(status_code=e.status_code, message=str(e))
                else:
                    raise OpenAIError(status_code=500, message=f"{str(e)}")

    async def aembedding(
        self,
        input: list,
        data: dict,
        model_response: ModelResponse,
        timeout: float,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        client=None,
        max_retries=None,
        logging_obj=None,
    ):
        response = None
        try:
            if client is None:
                openai_aclient = AsyncOpenAI(
                    api_key=api_key,
                    base_url=api_base,
                    http_client=litellm.aclient_session,
                    timeout=timeout,
                    max_retries=max_retries,
                )
            else:
                openai_aclient = client
            response = await openai_aclient.embeddings.create(**data, timeout=timeout)  # type: ignore
            stringified_response = response.model_dump()
            ## LOGGING
            logging_obj.post_call(
                input=input,
                api_key=api_key,
                additional_args={"complete_input_dict": data},
                original_response=stringified_response,
            )
            return convert_to_model_response_object(response_object=stringified_response, model_response_object=model_response, response_type="embedding")  # type: ignore
        except Exception as e:
            ## LOGGING
            logging_obj.post_call(
                input=input,
                api_key=api_key,
                original_response=str(e),
            )
            raise e

    def embedding(
        self,
        model: str,
        input: list,
        timeout: float,
        logging_obj,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        model_response: Optional[litellm.utils.EmbeddingResponse] = None,
        optional_params=None,
        client=None,
        aembedding=None,
    ):
        super().embedding()
        exception_mapping_worked = False
        try:
            model = model
            data = {"model": model, "input": input, **optional_params}
            max_retries = data.pop("max_retries", 2)
            if not isinstance(max_retries, int):
                raise OpenAIError(status_code=422, message="max retries must be an int")
            ## LOGGING
            logging_obj.pre_call(
                input=input,
                api_key=api_key,
                additional_args={"complete_input_dict": data, "api_base": api_base},
            )

            if aembedding == True:
                response = self.aembedding(data=data, input=input, logging_obj=logging_obj, model_response=model_response, api_base=api_base, api_key=api_key, timeout=timeout, client=client, max_retries=max_retries)  # type: ignore
                return response
            if client is None:
                openai_client = OpenAI(
                    api_key=api_key,
                    base_url=api_base,
                    http_client=litellm.client_session,
                    timeout=timeout,
                    max_retries=max_retries,
                )
            else:
                openai_client = client

            ## COMPLETION CALL
            response = openai_client.embeddings.create(**data, timeout=timeout)  # type: ignore
            ## LOGGING
            logging_obj.post_call(
                input=input,
                api_key=api_key,
                additional_args={"complete_input_dict": data},
                original_response=response,
            )

            return convert_to_model_response_object(response_object=response.model_dump(), model_response_object=model_response, response_type="embedding")  # type: ignore
        except OpenAIError as e:
            exception_mapping_worked = True
            raise e
        except Exception as e:
            if hasattr(e, "status_code"):
                raise OpenAIError(status_code=e.status_code, message=str(e))
            else:
                raise OpenAIError(status_code=500, message=str(e))

    async def aimage_generation(
        self,
        prompt: str,
        data: dict,
        model_response: ModelResponse,
        timeout: float,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        client=None,
        max_retries=None,
        logging_obj=None,
    ):
        response = None
        try:
            if client is None:
                openai_aclient = AsyncOpenAI(
                    api_key=api_key,
                    base_url=api_base,
                    http_client=litellm.aclient_session,
                    timeout=timeout,
                    max_retries=max_retries,
                )
            else:
                openai_aclient = client
            response = await openai_aclient.images.generate(**data, timeout=timeout)  # type: ignore
            stringified_response = response.model_dump()
            ## LOGGING
            logging_obj.post_call(
                input=prompt,
                api_key=api_key,
                additional_args={"complete_input_dict": data},
                original_response=stringified_response,
            )
            return convert_to_model_response_object(response_object=stringified_response, model_response_object=model_response, response_type="image_generation")  # type: ignore
        except Exception as e:
            ## LOGGING
            logging_obj.post_call(
                input=input,
                api_key=api_key,
                original_response=str(e),
            )
            raise e

    def image_generation(
        self,
        model: Optional[str],
        prompt: str,
        timeout: float,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        model_response: Optional[litellm.utils.ImageResponse] = None,
        logging_obj=None,
        optional_params=None,
        client=None,
        aimg_generation=None,
    ):
        exception_mapping_worked = False
        try:
            model = model
            data = {"model": model, "prompt": prompt, **optional_params}
            max_retries = data.pop("max_retries", 2)
            if not isinstance(max_retries, int):
                raise OpenAIError(status_code=422, message="max retries must be an int")

            if aimg_generation == True:
                response = self.aimage_generation(data=data, prompt=prompt, logging_obj=logging_obj, model_response=model_response, api_base=api_base, api_key=api_key, timeout=timeout, client=client, max_retries=max_retries)  # type: ignore
                return response

            if client is None:
                openai_client = OpenAI(
                    api_key=api_key,
                    base_url=api_base,
                    http_client=litellm.client_session,
                    timeout=timeout,
                    max_retries=max_retries,
                )
            else:
                openai_client = client

            ## LOGGING
            logging_obj.pre_call(
                input=prompt,
                api_key=openai_client.api_key,
                additional_args={
                    "headers": {"Authorization": f"Bearer {openai_client.api_key}"},
                    "api_base": openai_client._base_url._uri_reference,
                    "acompletion": True,
                    "complete_input_dict": data,
                },
            )

            ## COMPLETION CALL
            response = openai_client.images.generate(**data, timeout=timeout)  # type: ignore
            response = response.model_dump()  # type: ignore
            ## LOGGING
            logging_obj.post_call(
                input=prompt,
                api_key=api_key,
                additional_args={"complete_input_dict": data},
                original_response=response,
            )
            # return response
            return convert_to_model_response_object(response_object=response, model_response_object=model_response, response_type="image_generation")  # type: ignore
        except OpenAIError as e:

            exception_mapping_worked = True
            ## LOGGING
            logging_obj.post_call(
                input=prompt,
                api_key=api_key,
                additional_args={"complete_input_dict": data},
                original_response=str(e),
            )
            raise e
        except Exception as e:
            ## LOGGING
            logging_obj.post_call(
                input=prompt,
                api_key=api_key,
                additional_args={"complete_input_dict": data},
                original_response=str(e),
            )
            if hasattr(e, "status_code"):
                raise OpenAIError(status_code=e.status_code, message=str(e))
            else:
                raise OpenAIError(status_code=500, message=str(e))

    def audio_transcriptions(
        self,
        model: str,
        audio_file: BinaryIO,
        optional_params: dict,
        model_response: TranscriptionResponse,
        timeout: float,
        max_retries: int,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        client=None,
        logging_obj=None,
        atranscription: bool = False,
    ):
        data = {"model": model, "file": audio_file, **optional_params}
        if atranscription == True:
            return self.async_audio_transcriptions(
                audio_file=audio_file,
                data=data,
                model_response=model_response,
                timeout=timeout,
                api_key=api_key,
                api_base=api_base,
                client=client,
                max_retries=max_retries,
                logging_obj=logging_obj,
            )
        if client is None:
            openai_client = OpenAI(
                api_key=api_key,
                base_url=api_base,
                http_client=litellm.client_session,
                timeout=timeout,
                max_retries=max_retries,
            )
        else:
            openai_client = client
        response = openai_client.audio.transcriptions.create(
            **data, timeout=timeout  # type: ignore
        )

        stringified_response = response.model_dump()
        ## LOGGING
        logging_obj.post_call(
            input=audio_file.name,
            api_key=api_key,
            additional_args={"complete_input_dict": data},
            original_response=stringified_response,
        )
        hidden_params = {"model": "whisper-1", "custom_llm_provider": "openai"}
        final_response = convert_to_model_response_object(response_object=stringified_response, model_response_object=model_response, hidden_params=hidden_params, response_type="audio_transcription")  # type: ignore
        return final_response

    async def async_audio_transcriptions(
        self,
        audio_file: BinaryIO,
        data: dict,
        model_response: TranscriptionResponse,
        timeout: float,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        client=None,
        max_retries=None,
        logging_obj=None,
    ):
        response = None
        try:
            if client is None:
                openai_aclient = AsyncOpenAI(
                    api_key=api_key,
                    base_url=api_base,
                    http_client=litellm.aclient_session,
                    timeout=timeout,
                    max_retries=max_retries,
                )
            else:
                openai_aclient = client
            response = await openai_aclient.audio.transcriptions.create(
                **data, timeout=timeout
            )  # type: ignore
            stringified_response = response.model_dump()
            ## LOGGING
            logging_obj.post_call(
                input=audio_file.name,
                api_key=api_key,
                additional_args={"complete_input_dict": data},
                original_response=stringified_response,
            )
            hidden_params = {"model": "whisper-1", "custom_llm_provider": "openai"}
            return convert_to_model_response_object(response_object=stringified_response, model_response_object=model_response, hidden_params=hidden_params, response_type="audio_transcription")  # type: ignore
        except Exception as e:
            ## LOGGING
            logging_obj.post_call(
                input=input,
                api_key=api_key,
                original_response=str(e),
            )
            raise e

    async def ahealth_check(
        self,
        model: Optional[str],
        api_key: str,
        timeout: float,
        mode: str,
        messages: Optional[list] = None,
        input: Optional[list] = None,
        prompt: Optional[str] = None,
        organization: Optional[str] = None,
        api_base: Optional[str] = None,
    ):
        client = AsyncOpenAI(
            api_key=api_key,
            timeout=timeout,
            organization=organization,
            base_url=api_base,
        )
        if model is None and mode != "image_generation":
            raise Exception("model is not set")

        completion = None

        if mode == "completion":
            completion = await client.completions.with_raw_response.create(
                model=model,  # type: ignore
                prompt=prompt,  # type: ignore
            )
        elif mode == "chat":
            if messages is None:
                raise Exception("messages is not set")
            completion = await client.chat.completions.with_raw_response.create(
                model=model,  # type: ignore
                messages=messages,  # type: ignore
            )
        elif mode == "embedding":
            if input is None:
                raise Exception("input is not set")
            completion = await client.embeddings.with_raw_response.create(
                model=model,  # type: ignore
                input=input,  # type: ignore
            )
        elif mode == "image_generation":
            if prompt is None:
                raise Exception("prompt is not set")
            completion = await client.images.with_raw_response.generate(
                model=model,  # type: ignore
                prompt=prompt,  # type: ignore
            )
        else:
            raise Exception("mode not set")
        response = {}

        if completion is None or not hasattr(completion, "headers"):
            raise Exception("invalid completion response")

        if (
            completion.headers.get("x-ratelimit-remaining-requests", None) is not None
        ):  # not provided for dall-e requests
            response["x-ratelimit-remaining-requests"] = completion.headers[
                "x-ratelimit-remaining-requests"
            ]

        if completion.headers.get("x-ratelimit-remaining-tokens", None) is not None:
            response["x-ratelimit-remaining-tokens"] = completion.headers[
                "x-ratelimit-remaining-tokens"
            ]
        return response


class OpenAITextCompletion(BaseLLM):
    _client_session: httpx.Client

    def __init__(self) -> None:
        super().__init__()
        self._client_session = self.create_client_session()

    def validate_environment(self, api_key):
        headers = {
            "content-type": "application/json",
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    def completion(
        self,
        model_response: ModelResponse,
        api_key: str,
        model: str,
        messages: list,
        timeout: float,
        print_verbose: Optional[Callable] = None,
        api_base: Optional[str] = None,
        logging_obj=None,
        acompletion: bool = False,
        optional_params=None,
        litellm_params=None,
        logger_fn=None,
        client=None,
        organization: Optional[str] = None,
        headers: Optional[dict] = None,
    ):
        super().completion()
        exception_mapping_worked = False
        try:
            if headers is None:
                headers = self.validate_environment(api_key=api_key)
            if model is None or messages is None:
                raise OpenAIError(status_code=422, message=f"Missing model or messages")

            if (
                len(messages) > 0
                and "content" in messages[0]
                and type(messages[0]["content"]) == list
            ):
                prompt = messages[0]["content"]
            else:
                prompt = [message["content"] for message in messages]  # type: ignore

            # don't send max retries to the api, if set

            data = {"model": model, "prompt": prompt, **optional_params}
            max_retries = data.pop("max_retries", 2)
            ## LOGGING
            logging_obj.pre_call(
                input=messages,
                api_key=api_key,
                additional_args={
                    "headers": headers,
                    "api_base": api_base,
                    "complete_input_dict": data,
                },
            )
            if acompletion == True:
                if optional_params.get("stream", False):
                    return self.async_streaming(
                        logging_obj=logging_obj,
                        api_base=api_base,
                        api_key=api_key,
                        data=data,
                        headers=headers,
                        model_response=model_response,
                        model=model,
                        timeout=timeout,
                        max_retries=max_retries,
                        client=client,
                        organization=organization,
                    )
                else:
                    return self.acompletion(api_base=api_base, data=data, headers=headers, model_response=model_response, prompt=prompt, api_key=api_key, logging_obj=logging_obj, model=model, timeout=timeout, max_retries=max_retries, organization=organization, client=client)  # type: ignore
            elif optional_params.get("stream", False):
                return self.streaming(
                    logging_obj=logging_obj,
                    api_base=api_base,
                    api_key=api_key,
                    data=data,
                    headers=headers,
                    model_response=model_response,
                    model=model,
                    timeout=timeout,
                    max_retries=max_retries,  # type: ignore
                    client=client,
                    organization=organization,
                )
            else:
                if client is None:
                    openai_client = OpenAI(
                        api_key=api_key,
                        base_url=api_base,
                        http_client=litellm.client_session,
                        timeout=timeout,
                        max_retries=max_retries,  # type: ignore
                        organization=organization,
                    )
                else:
                    openai_client = client

                response = openai_client.completions.create(**data)  # type: ignore

                response_json = response.model_dump()
                ## LOGGING
                logging_obj.post_call(
                    input=prompt,
                    api_key=api_key,
                    original_response=response_json,
                    additional_args={
                        "headers": headers,
                        "api_base": api_base,
                    },
                )

                ## RESPONSE OBJECT
                return TextCompletionResponse(**response_json)
        except Exception as e:
            raise e

    async def acompletion(
        self,
        logging_obj,
        api_base: str,
        data: dict,
        headers: dict,
        model_response: ModelResponse,
        prompt: str,
        api_key: str,
        model: str,
        timeout: float,
        max_retries=None,
        organization: Optional[str] = None,
        client=None,
    ):
        try:
            if client is None:
                openai_aclient = AsyncOpenAI(
                    api_key=api_key,
                    base_url=api_base,
                    http_client=litellm.aclient_session,
                    timeout=timeout,
                    max_retries=max_retries,
                    organization=organization,
                )
            else:
                openai_aclient = client

            response = await openai_aclient.completions.create(**data)
            response_json = response.model_dump()
            ## LOGGING
            logging_obj.post_call(
                input=prompt,
                api_key=api_key,
                original_response=response,
                additional_args={
                    "headers": headers,
                    "api_base": api_base,
                },
            )
            ## RESPONSE OBJECT
            response_obj = TextCompletionResponse(**response_json)
            response_obj._hidden_params.original_response = json.dumps(response_json)
            return response_obj
        except Exception as e:
            raise e

    def streaming(
        self,
        logging_obj,
        api_key: str,
        data: dict,
        headers: dict,
        model_response: ModelResponse,
        model: str,
        timeout: float,
        api_base: Optional[str] = None,
        max_retries=None,
        client=None,
        organization=None,
    ):
        if client is None:
            openai_client = OpenAI(
                api_key=api_key,
                base_url=api_base,
                http_client=litellm.client_session,
                timeout=timeout,
                max_retries=max_retries,  # type: ignore
                organization=organization,
            )
        else:
            openai_client = client
        response = openai_client.completions.create(**data)
        streamwrapper = CustomStreamWrapper(
            completion_stream=response,
            model=model,
            custom_llm_provider="text-completion-openai",
            logging_obj=logging_obj,
            stream_options=data.get("stream_options", None),
        )

        for chunk in streamwrapper:
            yield chunk

    async def async_streaming(
        self,
        logging_obj,
        api_key: str,
        data: dict,
        headers: dict,
        model_response: ModelResponse,
        model: str,
        timeout: float,
        api_base: Optional[str] = None,
        client=None,
        max_retries=None,
        organization=None,
    ):
        if client is None:
            openai_client = AsyncOpenAI(
                api_key=api_key,
                base_url=api_base,
                http_client=litellm.aclient_session,
                timeout=timeout,
                max_retries=max_retries,
                organization=organization,
            )
        else:
            openai_client = client

        response = await openai_client.completions.create(**data)

        streamwrapper = CustomStreamWrapper(
            completion_stream=response,
            model=model,
            custom_llm_provider="text-completion-openai",
            logging_obj=logging_obj,
            stream_options=data.get("stream_options", None),
        )

        async for transformed_chunk in streamwrapper:
            yield transformed_chunk


class OpenAIFilesAPI(BaseLLM):
    """
    OpenAI methods to support for batches
    - create_file()
    - retrieve_file()
    - list_files()
    - delete_file()
    - file_content()
    - update_file()
    """

    def __init__(self) -> None:
        super().__init__()

    def get_openai_client(
        self,
        api_key: Optional[str],
        api_base: Optional[str],
        timeout: Union[float, httpx.Timeout],
        max_retries: Optional[int],
        organization: Optional[str],
        client: Optional[OpenAI] = None,
    ) -> OpenAI:
        received_args = locals()
        if client is None:
            data = {}
            for k, v in received_args.items():
                if k == "self" or k == "client":
                    pass
                elif k == "api_base" and v is not None:
                    data["base_url"] = v
                elif v is not None:
                    data[k] = v
            openai_client = OpenAI(**data)  # type: ignore
        else:
            openai_client = client

        return openai_client

    def create_file(
        self,
        create_file_data: CreateFileRequest,
        api_base: str,
        api_key: Optional[str],
        timeout: Union[float, httpx.Timeout],
        max_retries: Optional[int],
        organization: Optional[str],
        client: Optional[OpenAI] = None,
    ) -> FileObject:
        openai_client: OpenAI = self.get_openai_client(
            api_key=api_key,
            api_base=api_base,
            timeout=timeout,
            max_retries=max_retries,
            organization=organization,
            client=client,
        )
        response = openai_client.files.create(**create_file_data)
        return response


class OpenAIBatchesAPI(BaseLLM):
    """
    OpenAI methods to support for batches
    - create_batch()
    - retrieve_batch()
    - cancel_batch()
    - list_batch()
    """

    def __init__(self) -> None:
        super().__init__()

    def get_openai_client(
        self,
        api_key: Optional[str],
        api_base: Optional[str],
        timeout: Union[float, httpx.Timeout],
        max_retries: Optional[int],
        organization: Optional[str],
        client: Optional[OpenAI] = None,
    ) -> OpenAI:
        received_args = locals()
        if client is None:
            data = {}
            for k, v in received_args.items():
                if k == "self" or k == "client":
                    pass
                elif k == "api_base" and v is not None:
                    data["base_url"] = v
                elif v is not None:
                    data[k] = v
            openai_client = OpenAI(**data)  # type: ignore
        else:
            openai_client = client

        return openai_client

    def create_batch(
        self,
        create_batch_data: CreateBatchRequest,
        api_key: Optional[str],
        api_base: Optional[str],
        timeout: Union[float, httpx.Timeout],
        max_retries: Optional[int],
        organization: Optional[str],
        client: Optional[OpenAI] = None,
    ):
        openai_client: OpenAI = self.get_openai_client(
            api_key=api_key,
            api_base=api_base,
            timeout=timeout,
            max_retries=max_retries,
            organization=organization,
            client=client,
        )
        response = openai_client.batches.create(**create_batch_data)
        return response

    def retrieve_batch(
        self,
        retrieve_batch_data: RetrieveBatchRequest,
        api_key: Optional[str],
        api_base: Optional[str],
        timeout: Union[float, httpx.Timeout],
        max_retries: Optional[int],
        organization: Optional[str],
        client: Optional[OpenAI] = None,
    ):
        openai_client: OpenAI = self.get_openai_client(
            api_key=api_key,
            api_base=api_base,
            timeout=timeout,
            max_retries=max_retries,
            organization=organization,
            client=client,
        )
        response = openai_client.batches.retrieve(**retrieve_batch_data)
        return response

    def cancel_batch(
        self,
        cancel_batch_data: CancelBatchRequest,
        api_key: Optional[str],
        api_base: Optional[str],
        timeout: Union[float, httpx.Timeout],
        max_retries: Optional[int],
        organization: Optional[str],
        client: Optional[OpenAI] = None,
    ):
        openai_client: OpenAI = self.get_openai_client(
            api_key=api_key,
            api_base=api_base,
            timeout=timeout,
            max_retries=max_retries,
            organization=organization,
            client=client,
        )
        response = openai_client.batches.cancel(**cancel_batch_data)
        return response

    # def list_batch(
    #     self,
    #     list_batch_data: ListBatchRequest,
    #     api_key: Optional[str],
    #     api_base: Optional[str],
    #     timeout: Union[float, httpx.Timeout],
    #     max_retries: Optional[int],
    #     organization: Optional[str],
    #     client: Optional[OpenAI] = None,
    # ):
    #     openai_client: OpenAI = self.get_openai_client(
    #         api_key=api_key,
    #         api_base=api_base,
    #         timeout=timeout,
    #         max_retries=max_retries,
    #         organization=organization,
    #         client=client,
    #     )
    #     response = openai_client.batches.list(**list_batch_data)
    #     return response


class OpenAIAssistantsAPI(BaseLLM):
    def __init__(self) -> None:
        super().__init__()

    def get_openai_client(
        self,
        api_key: Optional[str],
        api_base: Optional[str],
        timeout: Union[float, httpx.Timeout],
        max_retries: Optional[int],
        organization: Optional[str],
        client: Optional[OpenAI] = None,
    ) -> OpenAI:
        received_args = locals()
        if client is None:
            data = {}
            for k, v in received_args.items():
                if k == "self" or k == "client":
                    pass
                elif k == "api_base" and v is not None:
                    data["base_url"] = v
                elif v is not None:
                    data[k] = v
            openai_client = OpenAI(**data)  # type: ignore
        else:
            openai_client = client

        return openai_client

    ### ASSISTANTS ###

    def get_assistants(
        self,
        api_key: Optional[str],
        api_base: Optional[str],
        timeout: Union[float, httpx.Timeout],
        max_retries: Optional[int],
        organization: Optional[str],
        client: Optional[OpenAI],
    ) -> SyncCursorPage[Assistant]:
        openai_client = self.get_openai_client(
            api_key=api_key,
            api_base=api_base,
            timeout=timeout,
            max_retries=max_retries,
            organization=organization,
            client=client,
        )

        response = openai_client.beta.assistants.list()

        return response

    ### MESSAGES ###

    def add_message(
        self,
        thread_id: str,
        message_data: MessageData,
        api_key: Optional[str],
        api_base: Optional[str],
        timeout: Union[float, httpx.Timeout],
        max_retries: Optional[int],
        organization: Optional[str],
        client: Optional[OpenAI] = None,
    ) -> OpenAIMessage:

        openai_client = self.get_openai_client(
            api_key=api_key,
            api_base=api_base,
            timeout=timeout,
            max_retries=max_retries,
            organization=organization,
            client=client,
        )

        thread_message: OpenAIMessage = openai_client.beta.threads.messages.create(  # type: ignore
            thread_id, **message_data  # type: ignore
        )

        response_obj: Optional[OpenAIMessage] = None
        if getattr(thread_message, "status", None) is None:
            thread_message.status = "completed"
            response_obj = OpenAIMessage(**thread_message.dict())
        else:
            response_obj = OpenAIMessage(**thread_message.dict())
        return response_obj

    def get_messages(
        self,
        thread_id: str,
        api_key: Optional[str],
        api_base: Optional[str],
        timeout: Union[float, httpx.Timeout],
        max_retries: Optional[int],
        organization: Optional[str],
        client: Optional[OpenAI] = None,
    ) -> SyncCursorPage[OpenAIMessage]:
        openai_client = self.get_openai_client(
            api_key=api_key,
            api_base=api_base,
            timeout=timeout,
            max_retries=max_retries,
            organization=organization,
            client=client,
        )

        response = openai_client.beta.threads.messages.list(thread_id=thread_id)

        return response

    ### THREADS ###

    def create_thread(
        self,
        metadata: Optional[dict],
        api_key: Optional[str],
        api_base: Optional[str],
        timeout: Union[float, httpx.Timeout],
        max_retries: Optional[int],
        organization: Optional[str],
        client: Optional[OpenAI],
        messages: Optional[Iterable[OpenAICreateThreadParamsMessage]],
    ) -> Thread:
        """
        Here's an example:
        ```
        from litellm.llms.openai import OpenAIAssistantsAPI, MessageData

        # create thread
        message: MessageData = {"role": "user", "content": "Hey, how's it going?"}
        openai_api.create_thread(messages=[message])
        ```
        """
        openai_client = self.get_openai_client(
            api_key=api_key,
            api_base=api_base,
            timeout=timeout,
            max_retries=max_retries,
            organization=organization,
            client=client,
        )

        data = {}
        if messages is not None:
            data["messages"] = messages  # type: ignore
        if metadata is not None:
            data["metadata"] = metadata  # type: ignore

        message_thread = openai_client.beta.threads.create(**data)  # type: ignore

        return Thread(**message_thread.dict())

    def get_thread(
        self,
        thread_id: str,
        api_key: Optional[str],
        api_base: Optional[str],
        timeout: Union[float, httpx.Timeout],
        max_retries: Optional[int],
        organization: Optional[str],
        client: Optional[OpenAI],
    ) -> Thread:
        openai_client = self.get_openai_client(
            api_key=api_key,
            api_base=api_base,
            timeout=timeout,
            max_retries=max_retries,
            organization=organization,
            client=client,
        )

        response = openai_client.beta.threads.retrieve(thread_id=thread_id)

        return Thread(**response.dict())

    def delete_thread(self):
        pass

    ### RUNS ###

    def run_thread(
        self,
        thread_id: str,
        assistant_id: str,
        additional_instructions: Optional[str],
        instructions: Optional[str],
        metadata: Optional[object],
        model: Optional[str],
        stream: Optional[bool],
        tools: Optional[Iterable[AssistantToolParam]],
        api_key: Optional[str],
        api_base: Optional[str],
        timeout: Union[float, httpx.Timeout],
        max_retries: Optional[int],
        organization: Optional[str],
        client: Optional[OpenAI],
    ) -> Run:
        openai_client = self.get_openai_client(
            api_key=api_key,
            api_base=api_base,
            timeout=timeout,
            max_retries=max_retries,
            organization=organization,
            client=client,
        )

        response = openai_client.beta.threads.runs.create_and_poll(  # type: ignore
            thread_id=thread_id,
            assistant_id=assistant_id,
            additional_instructions=additional_instructions,
            instructions=instructions,
            metadata=metadata,
            model=model,
            tools=tools,
        )

        return response
