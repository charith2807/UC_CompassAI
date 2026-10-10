"""Groq-preferred provider routing. Keys never leave environment reads."""
import json
import os
from time import perf_counter

ENV_KEYS={'groq':'GROQ_API_KEY','openai':'OPENAI_API_KEY','gemini':'GEMINI_API_KEY'}
BASE_URLS={'groq':'https://api.groq.com/openai/v1','openai':'https://api.openai.com/v1',
           'gemini':'https://generativelanguage.googleapis.com/v1beta/openai/'}
DEFAULT_MODELS={'groq':'openai/gpt-oss-20b','openai':'gpt-4o-mini','gemini':'gemini-3.8-flash'}

class ProviderUnavailable(RuntimeError):
    def __init__(self,attempts):
        self.attempts=attempts
        super().__init__('No configured provider completed the request; see safe error types')

def available(config=None):
    config=config or {}
    provider=config.get('llm_provider','auto')
    order=config.get('provider_order',['groq','openai','gemini']) if provider=='auto' else [provider]
    if any(p not in ENV_KEYS for p in order):raise ValueError('Unknown provider')
    return [p for p in dict.fromkeys(order) if os.getenv(ENV_KEYS[p])]

def provider_key_available(config=None):return bool(available(config))

class ProviderRouter:
    def __init__(self,config,clients=None):
        self.config=config
        self.clients=clients or {}  # Dependency injection for synthetic tests only.
    def configured(self):
        selected=self.config.get('llm_provider','auto')
        order=self.config.get('provider_order',['groq','openai','gemini']) if selected=='auto' else [selected]
        return [p for p in dict.fromkeys(order) if p in self.clients or os.getenv(ENV_KEYS[p])]
    def _client(self,provider):
        if provider not in self.clients:
            from openai import OpenAI
            self.clients[provider]=OpenAI(api_key=os.environ[ENV_KEYS[provider]],
               base_url=BASE_URLS[provider],timeout=self.config.get('provider_timeout_seconds',30),max_retries=0)
        return self.clients[provider]
    def complete(self,messages,schema=None):
        attempts=[];total_usage={'input_tokens':0,'output_tokens':0};total_cost=0.0
        choices=self.configured()
        for provider in choices:
            model=self.config.get('provider_models',DEFAULT_MODELS).get(provider,DEFAULT_MODELS[provider])
            parameters={'model':model,'messages':messages,'temperature':0,'max_tokens':1600}
            if provider=='groq' and 'gpt-oss' in model:parameters['reasoning_effort']='low'
            if provider=='gemini' and model.startswith('gemini-3'):parameters['reasoning_effort']='low'
            if schema is not None:
                parameters['response_format']={'type':'json_schema','json_schema':{
                    'name':'grounded_answer','strict':True,'schema':schema}}
            start=perf_counter();attempt={'provider':provider,'model':model}
            try:
                response=self._client(provider).chat.completions.create(**parameters)
                usage=response.usage
                prompt=int(getattr(usage,'prompt_tokens',0) or 0)
                completion=int(getattr(usage,'completion_tokens',0) or 0)
                total_usage['input_tokens']+=prompt;total_usage['output_tokens']+=completion
                prices=self.config.get('provider_prices',{}).get(provider,{})
                a,b=prices.get('input_per_million'),prices.get('output_per_million')
                cost=(prompt*a+completion*b)/1e6 if a is not None and b is not None else None
                total_cost=total_cost+cost if total_cost is not None and cost is not None else None
                content=response.choices[0].message.content
                if not content:raise ValueError('Empty provider response')
                if schema is not None:
                    import jsonschema
                    jsonschema.validate(json.loads(content),schema)
                attempt.update(status='completed',latency_ms=(perf_counter()-start)*1000,
                               input_tokens=prompt,output_tokens=completion,cost_usd=cost)
                attempts.append(attempt)
                return {'content':content,'provider':provider,'model':model,'attempts':attempts,
                        'usage':total_usage,'cost_usd':total_cost}
            except Exception as exc:
                # Never store provider exception messages, request headers, or API keys.
                attempt.update(status='failed',error_type=type(exc).__name__,latency_ms=(perf_counter()-start)*1000)
                attempts.append(attempt)
        raise ProviderUnavailable(attempts)
