# After running pip install haystack-ai "transformers[torch,sentencepiece]"

from haystack import Document
from haystack.components.readers import ExtractiveReader

# Create documents with various information
docs = [
    Document(content="Python is a popular programming language created by Guido van Rossum in 1991. It emphasizes code readability and simplicity."),
    Document(content="JavaScript was developed by Brendan Eich in 1995 and runs primarily in web browsers. It has become essential for web development."),
    Document(content="Java was released by Sun Microsystems in 1995. It follows the principle of 'write once, run anywhere' and is widely used in enterprise applications."),
    Document(content="C++ was developed by Bjarne Stroustrup in 1985 as an extension of C. It supports both procedural and object-oriented programming."),
    Document(content="The average salary for Python developers is $120,000 per year, while Java developers earn around $110,000 annually."),
]

# Initialize the reader
reader = ExtractiveReader(model="deepset/roberta-base-squad2")
# reader = ExtractiveReader(model="FacebookAI/roberta-base")bad
reader = ExtractiveReader(model="FacebookAI/roberta-large")

reader.warm_up()

# Define test questions
questions = [
    "Who created Python?",
    "When was JavaScript developed?",
    "What is the average salary for Python developers?",
    "Which language was released by Sun Microsystems?",
    "What principle does Java follow?",
    "Who developed C++?",
    "What programming paradigms does C++ support?",
    "Which language emphasizes code readability?",
    "What is JavaScript essential for?",
    "When was Python created?",
]

# Test each question
print("=" * 70)
print("EXTRACTIVE READER Q&A RESULTS")
print("=" * 70)

for question in questions:
    result = reader.run(query=question, documents=docs)
    
    print(f"\nQuestion: {question}")
    print("-" * 50)
    
    # Get valid answers (non-null)
    valid_answers = [a for a in result["answers"] if a.data is not None]
    
    if valid_answers:
        # Sort by score and show top 2 answers
        valid_answers.sort(key=lambda x: x.score, reverse=True)
        
        for i, answer in enumerate(valid_answers[:2], 1):  # Show top 2 answers
            print(f"  Answer {i}: {answer.data}")
            print(f"  Confidence: {answer.score:.2%}")
            if answer.document:
                # Show context around the answer
                start = max(0, answer.document_offset.start - 20)
                end = min(len(answer.document.content), answer.document_offset.end + 20)
                context = answer.document.content[start:end]
                # Highlight the answer in context with brackets
                answer_start = answer.document_offset.start - start
                answer_end = answer.document_offset.end - start
                highlighted = (
                    context[:answer_start] + 
                    "[" + context[answer_start:answer_end] + "]" + 
                    context[answer_end:]
                )
                print(f"  Context: ...{highlighted}...")
            print()
    else:
        print("  No answer found with sufficient confidence")

print("=" * 70)

# Summary statistics
print("\nSUMMARY STATISTICS:")
print("-" * 50)
all_scores = []
for question in questions:
    result = reader.run(query=question, documents=docs)
    valid_answers = [a for a in result["answers"] if a.data is not None]
    if valid_answers:
        best_score = max(a.score for a in valid_answers)
        all_scores.append(best_score)
        
if all_scores:
    print(f"Average best confidence: {sum(all_scores)/len(all_scores):.2%}")
    print(f"Highest confidence: {max(all_scores):.2%}")
    print(f"Lowest confidence: {min(all_scores):.2%}")
    print(f"Questions answered: {len(all_scores)}/{len(questions)}")