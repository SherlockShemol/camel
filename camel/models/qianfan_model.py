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
from typing import Any, Dict, Optional, Union

from camel.configs import QIANFAN_API_PARAMS, QianfanConfig
from camel.models.openai_compatible_model import OpenAICompatibleModel
from camel.types import ModelType
from camel.utils import (
    BaseTokenCounter,
    api_keys_required,
)


class QianfanModel(OpenAICompatibleModel):
    r"""Constructor for Qianfan backend with OpenAI compatibility.

    Args:
        model_type (Union[ModelType, str]): Model for which a backend is
            created, supported model can be found here:
            https://cloud.baidu.com/doc/QIANFANWORKSHOP/s/Wm9cvy6rl
        model_config_dict (Optional[Dict[str, Any]], optional): A dictionary
            that will be fed into:obj:`openai.ChatCompletion.create()`. If
            :obj:`None`, :obj:`QianfanConfig().as_dict()` will be used.
            (default: :obj:`None`)
        api_key (Optional[str], optional): The API key for authenticating with
            the Qianfan service. (default: :obj:`None`)
        url (Optional[str], optional): The url to the Qianfan service.
            If not provided, "https://qianfan.baidubce.com/v2/chat/completions"
            will be used.(default: :obj:`None`)
        token_counter (Optional[BaseTokenCounter], optional): Token counter to
            use for the model. If not provided, :obj:`OpenAITokenCounter(
            ModelType.GPT_4O_MINI)` will be used.
        timeout (Optional[float], optional): The timeout value in seconds for
            API calls. If not provided, will fall back to the MODEL_TIMEOUT
            environment variable or default to 180 seconds.
            (default: :obj:`None`)
        max_retries (Optional[int], optional): Maximum number of retries
            for API calls. (default: :obj:`None`)
        **kwargs: Additional model-specific parameters that will be passed
            to the model constructor.
    """

    @api_keys_required(
        [
            ("api_key", 'QIANFAN_API_KEY'),
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
        **kwargs,
    ) -> None:
        if model_config_dict is None:
            model_config_dict = QianfanConfig().as_dict()
        api_key = api_key or os.environ.get("QIANFAN_API_KEY")
        url = url or os.environ.get(
            "QIANFAN_API_BASE_URL",
            "https://qianfan.baidubce.com/v2",
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

    def check_model_config(self):
        r"""Check whether the model configuration contains any
        unexpected arguments to Qianfan API.

        Raises:
            ValueError: If the model configuration dictionary contains any
                unexpected arguments to Qianfan API.
        """
        for param in self.model_config_dict:
            if param not in QIANFAN_API_PARAMS:
                raise ValueError(
                    f"Unexpected argument `{param}` is "
                    "input into QIANFAN model backend."
                )
