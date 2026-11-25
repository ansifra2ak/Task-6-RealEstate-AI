"""Strict API request and response schemas, in source dataset units."""
from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Category = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]

class PropertyInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, json_schema_extra={
        'example': {'Area': 2500, 'Bedrooms': 3, 'Bathrooms': 2, 'Age': 15,
                    'Location': 'Suburb', 'Property_Type': 'House'}})
    Area: Annotated[int, Field(gt=0)]
    Bedrooms: Annotated[int, Field(ge=1)]
    Bathrooms: Annotated[int, Field(ge=1)]
    Age: Annotated[int, Field(ge=0)]
    Location: Category
    Property_Type: Category

class BatchInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    properties: Annotated[list[PropertyInput], Field(min_length=1, max_length=100)]

class Prediction(BaseModel):
    predicted_price: float
    units: str
    model_name: str
    model_version: str
    warnings: list[str]

class BatchPrediction(BaseModel):
    count: int
    predictions: list[Prediction]
