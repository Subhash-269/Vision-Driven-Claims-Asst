from transformers import AutoModelForQuestionAnswering, AutoTokenizer, pipeline

model_name = "deepset/roberta-base-squad2"
model_name = "distilbert-base-uncased-distilled-squad"
model_name = "bert-large-uncased-whole-word-masking-finetuned-squad"

# Load model and tokenizer, move model to GPU
model = AutoModelForQuestionAnswering.from_pretrained(model_name).to("cuda")
tokenizer = AutoTokenizer.from_pretrained(model_name)

nlp = pipeline('question-answering', model=model, tokenizer=tokenizer, device=0)
QA_input = {
    'question': 'Why is model conversion important?',
    'context': 'The option to convert models between FARM and transformers gives freedom to the user and let people easily switch between frameworks.'
}
res = nlp(QA_input)

print(res)