# Initialize Vertex AI
import os
import streamlit as st
import vertexai
import requests
from vertexai.generative_models import (
    Content,
    FunctionDeclaration,
    GenerationConfig,
    GenerativeModel,
    Image,
    Part,
    Tool,
    HarmCategory,
    HarmBlockThreshold
)
from google.cloud import secretmanager
import base64

# Define project information
PROJECT_ID = "your-project"  # @param {type:"string"}
LOCATION = "us-central1"  # @param {type:"string"}

vertexai.init(project=PROJECT_ID, location=LOCATION)


if 'output1' not in st.session_state:
    st.session_state.output1 = ""
if 'output2' not in st.session_state:
    st.session_state.output2 = ""
if 'output3' not in st.session_state:
    st.session_state.output3 = ""
if 'output4' not in st.session_state:
    st.session_state.output4 = ""
if 'output5' not in st.session_state:
    st.session_state.output5 = ""

st.header("✨  Multimodal Gemini 3.1 API - Vertex AI", divider="rainbow")
st.write("📍  **APPLE STRATEGIC ANALYSIS**")
tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["Alpha Vantage API", "Financial Statement PDF", "Image Analysis", "Audio and Video Analysis","Overall Analysis"]
)

with tab1:
    st.write("Using Gemini 3.1 Pro with function calling - Alpha Vantage API")

    ## ALPHA VANTAGE API: stock price, company overview, company news and news sentiment

    get_stock_price = FunctionDeclaration(
        name="get_stock_price",
        description="Fetch the current stock price of a given company",
        parameters={
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "Stock ticker symbol for a company",
                }
            },
        },
    )

    get_company_overview = FunctionDeclaration(
        name="get_company_overview",
        description="Get company details and other financial data",
        parameters={
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "Stock ticker symbol for a company",
                }
            },
        },
    )

    get_company_news = FunctionDeclaration(
        name="get_company_news",
        description="Get the latest news headlines for a given company.",
        parameters={
            "type": "object",
            "properties": {
                "tickers": {
                    "type": "string",
                    "description": "Stock ticker symbol for a company",
                }
            },
        },
    )

    get_news_with_sentiment = FunctionDeclaration(
        name="get_news_with_sentiment",
        description="Gets live and historical market news and sentiment data",
        parameters={
            "type": "object",
            "properties": {
                "news_topic": {
                    "type": "string",
                    "description": """News topic to learn about. Supported topics
                                include blockchain, earnings, ipo,
                                mergers_and_acquisitions, financial_markets,
                                economy_fiscal, economy_monetary, economy_macro,
                                energy_transportation, finance, life_sciences,
                                manufacturing, real_estate, retail_wholesale,
                                and technology""",
                },
            },
        },
    )

    #Alpha Vantage -- https://www.alphavantage.co/

    def access_secret_version(secret_version_id):
        client = secretmanager.SecretManagerServiceClient()
        response = client.access_secret_version(name=secret_version_id)
        return response.payload.data.decode('UTF-8')
    secret_version_id = f"projects/505484012957/secrets/ALPHA_VANTAGE/versions/latest"

    key=access_secret_version(secret_version_id)
    ALPHA_VANTAGE=os.getenv(key)

    def get_stock_price_from_api(content):
        url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={content['ticker']}&apikey={ALPHA_VANTAGE}"
        api_request = requests.get(url)
        return api_request.text


    def get_company_overview_from_api(content):
        url = f"https://www.alphavantage.co/query?function=OVERVIEW&symbol={content['ticker']}&apikey={ALPHA_VANTAGE}"
        api_response = requests.get(url)
        return api_response.text


    def get_company_news_from_api(content):
        url = f"https://www.alphavantage.co/query?function=NEWS_SENTIMENT&tickers={content['tickers']}&limit=20&sort=RELEVANCE&apikey={ALPHA_VANTAGE}"
        api_response = requests.get(url)
        return api_response.text


    def get_news_with_sentiment_from_api(content):
        url = f"https://www.alphavantage.co/query?function=NEWS_SENTIMENT&topics={content['news_topic']}&limit=20&sort=RELEVANCE&apikey={ALPHA_VANTAGE}"
        api_request = requests.get(url)
        return api_request.text

    function_handler = {
        "get_stock_price": get_stock_price_from_api,
        "get_company_overview": get_company_overview_from_api,
        "get_company_news": get_company_news_from_api,
        "get_news_with_sentiment": get_news_with_sentiment_from_api,
    }

    company_insights_tool = Tool(
        function_declarations=[
            get_stock_price,
            get_company_overview,
            get_company_news,
            get_news_with_sentiment,
        ],
    )


    model_10 = GenerativeModel(
        "gemini-3.1-pro",
        generation_config=GenerationConfig(temperature=0),
        tools=[company_insights_tool],safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        }
    )
    chat = model_10.start_chat(response_validation=False)


    def send_chat_message(prompt):
        print(prompt, "\n")
        # Send a chat message to the Gemini API
        response = chat.send_message(prompt)

        # Handle cases with multiple chained function calls
        function_calling_in_process = True
        while function_calling_in_process:
            import time
            time.sleep(1)
            # Extract the function call response
            function_call = response.candidates[0].content.parts[0].function_call

            # Check for a function call or a natural language response
            if function_call.name in function_handler.keys():
                # Extract the function call
                function_call = response.candidates[0].content.parts[0].function_call

                # Extract the function call name
                function_name = function_call.name

                # Extract the function call parameters
                params = {key: value for key, value in function_call.args.items()}

                # Invoke a function that calls an external API
                function_api_response = function_handler[function_name](params)[
                    :20000
                ]  # Stay within the input token limit

                # Send the API response back to Gemini, which will generate a natural language summary or another function call
                response = chat.send_message(
                    Part.from_function_response(
                        name=function_name,
                        response={"content": function_api_response},
                    ),
                )
            else:
                function_calling_in_process = False

        return response.text

    prompt_alpha="""
        You are a very competent finance professional.
        Give me the response in markdown format.
        - What is the company overview of AAPL?
        - What is the evolution of the AAPL stock price in the last 6 months?
        - What are the relevant news regarding AAPL, positive and negative?
        - What is the the AAPL news sentiment over the last 2 months?
        - What are the risks and challenges AAPL faces?
        """
    image_url = "https://storage.googleapis.com/bucket-15-storage/alpha.jpeg"
    st.image(image_url, width=300,caption="Financial API")    
    st.write("This tab generates a report based on the Alpha Vantage API, returning stock price evolution, company overview, news related to AAPL and sentiment analysis. ")

    st.subheader("Generate a report")
    st.markdown("""
    <style>
    div.stButton > button:first-child {
        background-color: rgb( 249, 217, 145 );
    }
    </style>""", unsafe_allow_html=True)

    generate_t2t = st.button("Generate my report", key="generate_t2t")

    if generate_t2t and prompt_alpha:
        # st.write(prompt)
        with st.spinner("Generating your report using Gemini 3.1 ..."):
            first_tab1, first_tab2 = st.tabs(["Report", "Prompt"])
            with first_tab1:
                alpha_vantage_output=send_chat_message(prompt_alpha)

                if alpha_vantage_output:
                    st.write("Your report:")
                    st.write(alpha_vantage_output)
                st.session_state.output1 = alpha_vantage_output
            with first_tab2:
                st.text(prompt_alpha)


with tab2:
    st.write("Using Gemini 3.1 - Financial Statement Analysis - PDF File")
    st.write("This tab analyzes AAPL financial statement related to Q2 2024 results")

    model_flash = GenerativeModel(
        "gemini-1.5-flash",
        generation_config=GenerationConfig(temperature=0)
    )
    pdf_file_uri = "gs://bucket-15-storage/FY24_Q2_Consolidated_Financial_Statements.pdf"

    prompt_finance = """
    You are a very competent finance professional and able to do mathematical calculations. 
    Give me the response in markdown format.
    If you don't know how to do it, just ignore and move ahead.
    - Calculate the Liquidity Index year over year. Is it good or bad ?
    - Calculate the Financial Leverage year over year. Is it good or bad ?
    - Calculate the Price/Profit year over year. Is it good or bad ?
    - Calculate the Gross Margin year over year. Is it good or bad ?
    - Calculate the Sales Growth year over year. Is it good or bad ?
    - Calculate the Debt year over year. Is it good or bad ?
    - Calculate the Long term debts year over year. Are they good or bad ?
    - Calculate the Net Margin year over year. Is it good or bad ?
    - Calculate the ROA (efficiency) year over year. Is it good or bad ?
    - Calculate the ROE (success) year over year. Is it good or bad ?
    """


    #uploaded_file = st.file_uploader("Upload your PDF file:", type='pdf')
    def display_pdf(file_path):
        with open(file_path, "rb") as f:
            pdf_bytes = f.read()
        base64_data = base64.b64encode(pdf_bytes).decode("utf-8")
        pdf_display = f'<iframe src="data:application/pdf;base64,{base64_data}" width="700" height="1000" type="application/pdf"></iframe>'
        st.markdown(pdf_display, unsafe_allow_html=True)


        # Specify the path to your existing PDF file
    pdf_path = "/home/theone/Downloads/CODE_other_models/Generative_AI/App_Competition/FY24_Q2_Consolidated_Financial_Statements.pdf"  # Replace with your actual path

        # Display the PDF
    display_pdf(pdf_path)


    
    pdf_file = Part.from_uri(pdf_file_uri, mime_type="application/pdf") ## FIX
    contents_finance = [pdf_file, prompt_finance]

    st.subheader("Generate PDF Analysis")
    st.markdown("""
    <style>
    div.stButton > button:first-child {
        background-color: rgb( 249, 217, 145 );
    }
    </style>""", unsafe_allow_html=True)

    generate_t2t2 = st.button("Generate PDF analysis", key="generate_t2t2")

    if generate_t2t2 and prompt_finance:
        # st.write(prompt)
        with st.spinner("Generating your analysis using Gemini 3.1 ..."):
            first_tab1, first_tab2 = st.tabs(["PDF Analysis", "Prompt"])
            with first_tab1:
                finance_output = model_flash.generate_content(contents_finance,safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        })


                if finance_output:
                    st.write("Your analysis:")
                    st.write(finance_output.text)
                    st.session_state.output2=finance_output.text
            with first_tab2:
                st.text(prompt_finance)

with tab3:
    st.write("Using Gemini 3.1 - Image Analysis of Apple Price Table")
    st.write("This tab analyzes a price table of Apple products around the world")

    model_flash = GenerativeModel(
        "gemini-1.5-flash",
        generation_config=GenerationConfig(temperature=0)
    )

    ## QUALITATIVE ANALYSIS OF APPLE MARKETING STRATEGY VIA IMAGES

    def load_image(url):
        return Part.from_uri(url, mime_type="image/jpeg")

    # DATA OBTAINED VIA KAGGLE: https://www.kaggle.com/datasets/prasertk/apple-product-price-list-from-26-countries-2022/data

    image_prices1 = "gs://bucket-15-storage/pricing.jpeg"
    image_prices = load_image(image_prices1)


    prompt_images = """You are a very competent finance professional.
                Give me the response in markdown format.
                For each product, tell me which country has the most expensive price.
                """

    contents_images = [
        image_prices,
        prompt_images,
    ]


    image_url = "https://storage.googleapis.com/bucket-15-storage/pricing.jpeg"
    st.image(image_url, width=680,caption="Apple prices across the world")    

    st.subheader("Generate a report")
    st.markdown("""
    <style>
    div.stButton > button:first-child {
        background-color: rgb( 249, 217, 145 );
    }
    </style>""", unsafe_allow_html=True)

    generate_t2t3 = st.button("Generate my report", key="generate_t2t3")

    if generate_t2t3 and prompt_alpha:
        # st.write(prompt)
        with st.spinner("Generating your report using Gemini 3.1 ..."):
            first_tab1, first_tab2 = st.tabs(["Report", "Prompt"])
            with first_tab1:
                response_images = model_flash.generate_content(contents_images)
                if response_images:
                    st.write("Your report:")
                    st.write(response_images.text)
                    st.session_state.output3 = response_images.text
            with first_tab2:
                st.text(prompt_images)

with tab4:
    tab1, tab2 = st.tabs(["Audio", "Video"])
    with tab1:

        st.write("Using Gemini 3.1 - Audio Analysis of Q2 Earnings Call")

        model_flash = GenerativeModel(
            "gemini-1.5-flash",
            generation_config=GenerationConfig(temperature=0)
        )

        ## ANALYSIS OF VIDEO - EARNINGS REPORT Q2 2024
        video = Part.from_uri(
            uri="gs://bucket-15-storage/output22.mp4",
            mime_type="video/mp4",
        )
        vide_desc_uri = "gs://bucket-15-storage/output22.mp4"
        video_desc_url = (
            "https://storage.googleapis.com/" + vide_desc_uri.split("gs://")[1]
        )
        vide_desc_img = Part.from_uri(vide_desc_uri, mime_type="video/mp4")
        st.video(video_desc_url)
        st.write("Our expectation: Generate the description of the audio")
        prompt_earnings = """You are a very competent finance professional.
        Give me the response in markdown format.
        - What were the key takeaways from the CEO and CFO's statements regarding Q2 2024 earnings?
        - What is the sentiment of each one ? Positive, neutral or negative ?
        """

        st.markdown("""
        <style>
        div.stButton > button:first-child {
            background-color: rgb( 249, 217, 145 );
        }
        </style>""", unsafe_allow_html=True)

        generate_t2t4 = st.button("Generate audio description", key="generate_t2t4")

        if generate_t2t4 and prompt_earnings:
            with st.spinner("Generating your analysis using Gemini 3.1 ..."):
                first_tab1, first_tab2 = st.tabs(["Report", "Prompt"])
                with first_tab1:
                    contents_earnings = [prompt_earnings, video]
                    responses_earnings = model_flash.generate_content(contents_earnings, stream=True)
                    responses_earnings_output=""
                    for response in responses_earnings:
                        responses_earnings_output=responses_earnings_output+response.text
                    if responses_earnings_output:
                        st.write("Your report:")
                        st.markdown(responses_earnings_output)
                        st.session_state.output4=responses_earnings_output
                with first_tab2:
                    st.text(prompt_earnings)
    with tab2:
        st.write("Using Gemini 3.1 - Video Analysis of Marketing Campaign")

        model_flash = GenerativeModel(
            "gemini-1.5-flash",
            generation_config=GenerationConfig(temperature=0)
        )

        ## ANALYSIS OF VIDEO - EARNINGS REPORT Q2 2024
        video = Part.from_uri(
            uri="gs://bucket-15-storage/Introducing iPhone 15 Pro Apple.mp4",
            mime_type="video/mp4",
        )
        vide_desc_uri = "gs://bucket-15-storage/Introducing iPhone 15 Pro Apple.mp4"
        video_desc_url = (
            "https://storage.googleapis.com/" + vide_desc_uri.split("gs://")[1]
        )
        vide_desc_img = Part.from_uri(vide_desc_uri, mime_type="video/mp4")
        st.video(video_desc_url)
        st.write("Our expectation: Generate the description and insights from the video")
        ## ANALYSIS OF VIDEO - MARKETING CAMPAIGN


        prompt_mkt = """
        You are a very competent marketing professional.
        Give me the response in markdown format.
        - What is in the video?
        - What is the video strategy to sell the Apple product?
        - What is the emotional appeal?
        """

        st.markdown("""
        <style>
        div.stButton > button:first-child {
            background-color: rgb( 249, 217, 145 );
        }
        </style>""", unsafe_allow_html=True)

        generate_t2t5 = st.button("Generate video description", key="generate_t2t5")

        if generate_t2t5 and prompt_mkt:
            with st.spinner("Generating your analysis using Gemini 3.1 ..."):
                first_tab1, first_tab2 = st.tabs(["Report", "Prompt"])
                with first_tab1:
                    contents_mkt = [prompt_mkt, video]
                    responses_mkt = model_flash.generate_content(contents_mkt, stream=True)
                    responses_mkt_output=""
                    for response in responses_mkt:
                        responses_mkt_output=responses_mkt_output+response.text
                    if responses_mkt_output:
                        st.write("Your report:")
                        st.markdown(responses_mkt_output)
                        st.session_state.output5 = responses_mkt_output
                with first_tab2:
                    st.text(prompt_mkt)

with tab5:
    st.write("Using Gemini 3.1 - Overall Strategic Analysis of Apple Q2 2024 Data")
    st.write("\n")
    st.write(":green[**For best results, you must carry out all other analyzes beforehand.**]")

    Alpha_Vantage_Output=st.session_state.output1
    Financial_statement_Output=st.session_state.output2        
    Image_Output=st.session_state.output3
    Audio_Output=st.session_state.output4
    Video_Output=st.session_state.output5


    model_flash = GenerativeModel(
        "gemini-1.5-flash",
        generation_config=GenerationConfig(temperature=0.3)
    )

    contents_all = (
    f"These are Apple overview, its price evolution in the last 6 months, its relevante news, "
    f"and sentiment of investors and news in the last 6 months: {Alpha_Vantage_Output}\n"
    f"This is the report of the financial statement: {Financial_statement_Output}\n"
    f"This is Apple pricing strategy: {Image_Output}\n"
    f"These are the CEO and CFO statements regarding Q2 2024 earnings: {Audio_Output}\n"
    f"Tell me if you see any inconsistencies or contradictions, given the financial statement and the current news.\n"
    f"Given the Marketing campaign: {Video_Output} and financial statement\n"
    "and what CEO and CFO said, how could the Marketing strategy be improved?"
)

    st.subheader("Generate the final report")
    st.markdown("""
    <style>
    div.stButton > button:first-child {
        background-color: rgb( 249, 217, 145 );
    }
    </style>""", unsafe_allow_html=True)
    generate_t2t6 = st.button("Generate my report", key="generate_t2t6")

    if generate_t2t6 and prompt_alpha:
        # st.write(prompt)
        with st.spinner("Generating your consolidated report using Gemini 3.1 ..."):
            first_tab1, first_tab2 = st.tabs(["Report", "Prompt"])
            with first_tab1:
                responses_all = model_flash.generate_content(contents_all, stream=True)
                responses_all_output=""
                for response in responses_all:
                    responses_all_output=responses_all_output+response.text
                if responses_all_output:
                    st.write("Your report:")
                    st.markdown(responses_all_output)
            with first_tab2:
                st.text(contents_all)

